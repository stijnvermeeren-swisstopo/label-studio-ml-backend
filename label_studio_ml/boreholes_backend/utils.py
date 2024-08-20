"""Utility functions for boreholes_backend."""

import logging
import uuid

from stratigraphy.util.predictions import BoreholeMetaData, FilePredictions, LayerPrediction

logger = logging.getLogger(__name__)


def convert_to_ls(pixel_position: int, original_length: int):
    """Convert the pixel position to the label-studio format."""
    return 100 * pixel_position / original_length


def build_model_predictions(file_predictions: FilePredictions, page_number: int, ls_page_width: int) -> list[dict]:
    """Build the label-studio predictions object from the stratygraphy.prediction.PagePrediction object.

    Note: Could become a method of the PagePrediction class.

    Args:
        prediction (FilePredictions): The prediction object from the stratigraphy pipeline.
        page_number (int): The page number to extract the predictions from. 0-based.
        ls_page_width (int): The page width as obtained by label_studio. Differs by a scaling factor from the page
                             width in the predictions object.

    Returns:
        list[dict]: The label-studio predictions object.
    """
    pre_annotation_result = []
    layers_with_depth_intervals = []
    scale_factor = ls_page_width / file_predictions.page_sizes[page_number]["width"]

    # extract metadata. For now coordinates only
    metadata_prediction = file_predictions.metadata
    coordinates = metadata_prediction.coordinates
    if coordinates is not None and page_number + 1 == coordinates.page:
        label = "Coordinates"
        value = {
            "x": convert_to_ls(coordinates.rect.x0, file_predictions.page_sizes[page_number]["width"]),
            "y": convert_to_ls(coordinates.rect.y0, file_predictions.page_sizes[page_number]["height"]),
            "width": convert_to_ls(
                coordinates.rect.width,
                file_predictions.page_sizes[page_number]["width"],
            ),
            "height": convert_to_ls(
                coordinates.rect.height,
                file_predictions.page_sizes[page_number]["height"],
            ),
            "rotation": 0,
        }
        metadata_id = uuid.uuid4().hex
        pre_annotation_result.extend(
            create_metadata_ls_result(
                metadata_prediction, file_predictions, page_number, value, label, metadata_id=metadata_id, scale_factor=scale_factor
            )
        )

    # extract layers
    layers = filter_layers_by_page(file_predictions.layers, page_number)
    for layer in layers:
        for label in ["Material Description", "Depth Interval"]:
            if label == "Material Description":
                value = {
                    "x": convert_to_ls(layer.material_description.rect.x0, file_predictions.page_sizes[page_number]["width"]),
                    "y": convert_to_ls(layer.material_description.rect.y0, file_predictions.page_sizes[page_number]["height"]),
                    "width": convert_to_ls(
                        layer.material_description.rect.width,
                        file_predictions.page_sizes[page_number]["width"],
                    ),
                    "height": convert_to_ls(
                        layer.material_description.rect.height,
                        file_predictions.page_sizes[page_number]["height"],
                    ),
                    "rotation": 0,
                }
            elif label == "Depth Interval":
                if layer.depth_interval is None:
                    continue

                elif layer.depth_interval.start is None and layer.depth_interval.end is not None:
                    layers_with_depth_intervals.append(layer.id.hex)
                    value = {
                        "x": convert_to_ls(layer.depth_interval.end.rect.x0, file_predictions.page_sizes[page_number]["width"]),
                        "y": convert_to_ls(
                            layer.depth_interval.end.rect.y0,
                            file_predictions.page_sizes[page_number]["height"],
                        ),
                        "width": convert_to_ls(
                            layer.depth_interval.end.rect.width,
                            file_predictions.page_sizes[page_number]["width"],
                        ),
                        "height": convert_to_ls(
                            layer.depth_interval.end.rect.height,
                            file_predictions.page_sizes[page_number]["height"],
                        ),
                        "rotation": 0,
                    }

                elif layer.depth_interval.start is not None and layer.depth_interval.end is not None:
                    layers_with_depth_intervals.append(layer.id.hex)
                    value = {
                        "x": convert_to_ls(
                            layer.depth_interval.background_rect.x0,
                            file_predictions.page_sizes[page_number]["width"],
                        ),
                        "y": convert_to_ls(
                            layer.depth_interval.background_rect.y0,
                            file_predictions.page_sizes[page_number]["height"],
                        ),
                        "width": convert_to_ls(
                            layer.depth_interval.background_rect.width,
                            file_predictions.page_sizes[page_number]["width"],
                        ),
                        "height": convert_to_ls(
                            layer.depth_interval.background_rect.height,
                            file_predictions.page_sizes[page_number]["height"],
                        ),
                        "rotation": 0,
                    }

                else:
                    logger.warning(f"Depth interval for layer {layer.id.hex} is not complete.")
                    continue

            pre_annotation_result.extend(create_ls_result(layer, file_predictions, page_number, value, label, scale_factor))

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


def filter_layers_by_page(layers: list[LayerPrediction], page_number: int) -> list[LayerPrediction]:
    """Filter layers by page number.
    
    Args:
        layers (list[LayerPrediction]): The list of layer predictions.
        page_number (int): The page number to filter by. 0-based.

    Returns:
        list[LayerPrediction]: The filtered list of layer predictions
    """
    return [layer for layer in layers if layer.material_description.page_number == page_number + 1]

def create_ls_result(
    layer: LayerPrediction, file_prediction: FilePredictions, page_number: int, value: dict, label: str, scale_factor: float
) -> list[dict]:
    """Generate the label-studio predictions object for a single layer and label.

    Args:
        layer (LayerPrediction): The layer prediction object.
        file_prediction (FilePredictions): The page prediction object.
        value (dict): The value object for the label.
        label (str): The label name.
        scale_factor (float): Scaling factor applied on the png images shown in label-studio.

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
        pre_annotation["original_width"] = int(
            file_prediction.page_sizes[page_number]["width"] * scale_factor
        )  # unclear if this key is required
        pre_annotation["original_height"] = int(file_prediction.page_sizes[page_number]["height"] * scale_factor)
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
    metadata_prediction: BoreholeMetaData,
    file_prediction: FilePredictions,
    page_number: int,
    value: dict,
    label: str,
    metadata_id: str,
    scale_factor: float,
) -> list[dict]:
    """Generate the label-studio predictions object for a single metadata object and label.

    Args:
        metadata_prediction (BoreholeMetaData): The metadata_prediction prediction object.
        file_prediction (FilePredictions): The file prediction object.
        page_number (int): The page number to filter by. 0-based.
        value (dict): The value object for the label.
        label (str): The label name.
        metadata_id (str): The id of the metadata object.
        scale_factor (float): Scaling factor applied on the png images shown in label-studio.

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
        pre_annotation["original_width"] = int(
            file_prediction.page_sizes[page_number]["width"] * scale_factor
        )  # unclear if this key is required
        pre_annotation["original_height"] = int(file_prediction.page_sizes[page_number]["height"] * scale_factor)
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
