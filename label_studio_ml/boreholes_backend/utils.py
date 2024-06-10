"""Utility functions for boreholes_backend."""

import logging
import uuid

from stratigraphy.util.predictions import BoreholeMetaData, FilePredictions, LayerPrediction, PagePredictions

logger = logging.getLogger(__name__)


def convert_to_ls(pixel_position: int, original_length: int):
    """Convert the pixel position to the label-studio format."""
    return 100 * pixel_position / original_length


def build_model_predictions(prediction: FilePredictions, page_number: int) -> list[dict]:
    """Build the label-studio predictions object from the stratygraphy.prediction.PagePrediction object.

    Note: Could become a method of the PagePrediction class.

    Args:
        prediction (FilePredictions): The prediction object from the stratigraphy pipeline.
        page_number (int): The page number to extract the predictions from.

    Returns:
        list[dict]: The label-studio predictions object.
    """
    pre_annotation_result = []
    layers_with_depth_intervals = []
    page_prediction = prediction.pages[page_number]

    # extract metadata for the first page
    if page_number == 0:
        metadata_prediction = prediction.metadata
        coordinates = metadata_prediction.coordinates
        if coordinates is not None:
            label = "Coordinates"
            value = {
                "x": convert_to_ls(coordinates.rect.x0, page_prediction.page_width),
                "y": convert_to_ls(coordinates.rect.y0, page_prediction.page_height),
                "width": convert_to_ls(
                    coordinates.rect.width,
                    page_prediction.page_width,
                ),
                "height": convert_to_ls(
                    coordinates.rect.height,
                    page_prediction.page_height,
                ),
                "rotation": 0,
            }
            metadata_id = uuid.uuid4().hex
            pre_annotation_result.extend(
                create_metadata_ls_result(metadata_prediction, page_prediction, value, label, metadata_id=metadata_id)
            )

    # extract layers
    for layer in page_prediction.layers:
        for label in ["Material Description", "Depth Interval"]:
            if label == "Material Description":
                value = {
                    "x": convert_to_ls(layer.material_description.rect.x0, page_prediction.page_width),
                    "y": convert_to_ls(layer.material_description.rect.y0, page_prediction.page_height),
                    "width": convert_to_ls(
                        layer.material_description.rect.width,
                        page_prediction.page_width,
                    ),
                    "height": convert_to_ls(
                        layer.material_description.rect.height,
                        page_prediction.page_height,
                    ),
                    "rotation": 0,
                }
            elif label == "Depth Interval":
                if layer.depth_interval is None:
                    continue

                elif layer.depth_interval.start is None and layer.depth_interval.end is not None:
                    layers_with_depth_intervals.append(layer.id.hex)
                    value = {
                        "x": convert_to_ls(layer.depth_interval.end.rect.x0, page_prediction.page_width),
                        "y": convert_to_ls(
                            layer.depth_interval.end.rect.y0,
                            page_prediction.page_height,
                        ),
                        "width": convert_to_ls(
                            layer.depth_interval.end.rect.width,
                            page_prediction.page_width,
                        ),
                        "height": convert_to_ls(
                            layer.depth_interval.end.rect.height,
                            page_prediction.page_height,
                        ),
                        "rotation": 0,
                    }

                elif layer.depth_interval.start is not None and layer.depth_interval.end is not None:
                    layers_with_depth_intervals.append(layer.id.hex)
                    value = {
                        "x": convert_to_ls(
                            layer.depth_interval.background_rect.x0,
                            page_prediction.page_width,
                        ),
                        "y": convert_to_ls(
                            layer.depth_interval.background_rect.y0,
                            page_prediction.page_height,
                        ),
                        "width": convert_to_ls(
                            layer.depth_interval.background_rect.width,
                            page_prediction.page_width,
                        ),
                        "height": convert_to_ls(
                            layer.depth_interval.background_rect.height,
                            page_prediction.page_height,
                        ),
                        "rotation": 0,
                    }

                else:
                    logger.warning(f"Depth interval for layer {layer.id.hex} is not complete.")
                    continue

            pre_annotation_result.extend(create_ls_result(layer, page_prediction, value, label))

    for layer_id in layers_with_depth_intervals:
        relation = {
            "type": "relation",
            "to_id": f"{layer_id}_Depth Interval",
            "from_id": f"{layer_id}_Material Description",
            "direction": "right",
        }
        pre_annotation_result.append(relation)

    model_predictions = {}
    model_predictions["model_version"] = "0.0.1"
    model_predictions["result"] = pre_annotation_result
    return [model_predictions]


def create_ls_result(layer: LayerPrediction, page_prediction: PagePredictions, value: dict, label: str) -> list[dict]:
    """Generate the label-studio predictions object for a single layer and label.

    Args:
        layer (LayerPrediction): The layer prediction object.
        page_prediction (PagePredictions): The page prediction object.
        value (dict): The value object for the label.
        label (str): The label name.

    Returns:
        list[dict]: The label-studio predictions object.
    """
    types = ["rectangle", "labels", "textarea"]
    pre_annotation_result = []
    for _type in types:
        pre_annotation = {}
        pre_annotation["id"] = layer.id.hex + f"_{label}"
        pre_annotation["type"] = _type
        pre_annotation["value"] = value.copy()
        pre_annotation["original_widht"] = int(page_prediction.page_width * 3)  # we used a scale factor of three
        pre_annotation["original_height"] = int(page_prediction.page_height * 3)  # we used a scale factor of three
        pre_annotation["image_rotation"] = 0
        pre_annotation["origin"] = "manual"
        if _type == "rectangle":
            pre_annotation["from_name"] = "bbox"
            pre_annotation["to_name"] = "image"
        elif _type == "labels":
            pre_annotation["from_name"] = "label"
            pre_annotation["to_name"] = "image"
            pre_annotation["value"]["labels"] = [label]
        elif _type == "textarea":
            pre_annotation["from_name"] = "transcription"
            pre_annotation["to_name"] = "image"
            if label == "Material Description":
                pre_annotation["value"]["text"] = [layer.material_description.text]
            elif label == "Depth Interval":
                if layer.depth_interval.start is None:
                    pre_annotation["value"]["text"] = [f"start: 0 end: {layer.depth_interval.end.value}"]
                else:
                    pre_annotation["value"]["text"] = [
                        f"start: {layer.depth_interval.start.value} end: {layer.depth_interval.end.value}"
                    ]
        pre_annotation_result.append(pre_annotation)
    return pre_annotation_result


def create_metadata_ls_result(
    metadata_prediction: BoreholeMetaData, page_prediction: PagePredictions, value: dict, label: str, metadata_id: str
) -> list[dict]:
    """Generate the label-studio predictions object for a single metadata object and label.

    Args:
        metadata_prediction (BoreholeMetaData): The metadata_prediction prediction object.
        page_prediction (PagePredictions): The page prediction object.
        value (dict): The value object for the label.
        label (str): The label name.
        metadata_id (str): The id of the metadata object.

    Returns:
        list[dict]: The label-studio predictions object.
    """
    types = ["rectangle", "labels", "textarea"]
    pre_annotation_result = []
    for _type in types:
        pre_annotation = {}
        pre_annotation["id"] = metadata_id
        pre_annotation["type"] = _type
        pre_annotation["value"] = value.copy()
        pre_annotation["original_widht"] = int(page_prediction.page_width * 3)  # we used a scale factor of three
        pre_annotation["original_height"] = int(page_prediction.page_height * 3)  # we used a scale factor of three
        pre_annotation["image_rotation"] = 0
        pre_annotation["origin"] = "manual"
        if _type == "rectangle":
            pre_annotation["from_name"] = "bbox"
            pre_annotation["to_name"] = "image"
        elif _type == "labels":
            pre_annotation["from_name"] = "label"
            pre_annotation["to_name"] = "image"
            pre_annotation["value"]["labels"] = [label]
        elif _type == "textarea":
            pre_annotation["from_name"] = "transcription"
            pre_annotation["to_name"] = "image"
            if label == "Coordinates":
                pre_annotation["value"]["text"] = [str(metadata_prediction.coordinates)]
            else:
                print("Metadata label not found.")
        pre_annotation_result.append(pre_annotation)
    return pre_annotation_result
