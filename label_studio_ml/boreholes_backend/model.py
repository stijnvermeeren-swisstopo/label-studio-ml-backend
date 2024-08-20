"""Custom ML Model for the boreholes backend."""

from pathlib import Path
from typing import Dict, List, Optional

from stratigraphy.main import start_pipeline
from utils import build_model_predictions

from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.response import ModelResponse
from PIL import Image


class LayerExtractionModel(LabelStudioMLBase):
    """Custom ML Backend model."""

    def setup(self):
        """Configuration of model parameters."""
        self.set("model_version", "0.0.1")

    def predict(self, tasks: List[Dict], context: Optional[Dict] = None, **kwargs) -> ModelResponse:
        """Prediction inference logic.

        :param tasks: [Label Studio tasks in JSON format](https://labelstud.io/guide/task_format.html)
        :param context: [Label Studio context in JSON format](https://labelstud.io/guide/ml_create#Implement-prediction-logic)
        :return model_response
            ModelResponse(predictions=predictions) with
            predictions: [Predictions array in JSON format](https://labelstud.io/guide/export.html#Label-Studio-JSON-format-of-annotated-tasks)
        """
        print(f"""\
        Run prediction on {tasks}""")

        png_path = tasks[0]["data"]["ocr"].split("=")[-1]
        file_name = png_path.split("/")[-1]
        project_name = tasks[0]["data"]["ocr"].split("/")[-2]
        file_name, page_number = file_name.split("_")
        page_number = int(page_number.split(".")[0])  # page_number is 0-based
        file_name = file_name + ".pdf"
        # Adjust the path below for now. Make sure volume is mounted in docker container.
        # TODO: See what of these paths is actually needed. Renato mentioned 
        # that some of these might be redundant.
        input_directory = Path("/data/pdf/") / project_name / file_name
        ground_truth_path = Path("/data/validation/ground_truth.json")
        out_directory = Path("/data/_temp/")
        predictions_path = Path("/data/_temp/predictions.json")
        skip_draw_predictions = True

        prediction = start_pipeline(
            input_directory=input_directory,
            ground_truth_path=ground_truth_path,
            out_directory=out_directory,
            predictions_path=predictions_path,
            skip_draw_predictions=skip_draw_predictions,
        )
        try:
            pdf_file_name = list(prediction.keys())[0]
            prediction = prediction[pdf_file_name]
            # get image width from png file to retrieve information about image scaling from the pdf
            image = Image.open(Path('/data') / png_path) 
            ls_page_width = image.size[0]
            model_predictions = build_model_predictions(prediction, page_number, ls_page_width=ls_page_width)
        except IndexError:
            print("No prediction found.")
            model_predictions = []
        return ModelResponse(predictions=model_predictions)

    def fit(self, event, data, **kwargs):
        """This method is called each time an annotation is created or updated.

        You can run your logic here to update the model and persist it to the cache
        It is not recommended to perform long-running operations here, as it will block the main thread
        Instead, consider running a separate process or a thread (like RQ worker) to perform the training
        :param event: event type can be ('ANNOTATION_CREATED', 'ANNOTATION_UPDATED')
        :param data: the payload received from the event (check [Webhook event reference](https://labelstud.io/guide/webhook_reference.html))
        """
        # Idea: Adjust the predictions objects based on the new annotation.
        # I.e. adjust the rectangles, get the depth-intervals (if missing), correct the text,
        # and reorder the depth-intervals (i.e. assignment of depth-intervals to material descriptions)
        # Would require to save the predictions somewhere. Potentially they will be saved twice.
        # Would require a model object which is connected to the data. --> I don't like that.

        # use cache to retrieve the data from the previous fit() runs
        old_data = self.get("my_data")
        old_model_version = self.get("model_version")
        print(f"Old data: {old_data}")
        print(f"Old model version: {old_model_version}")

        # store new data to the cache
        self.set("my_data", "my_new_data_value")
        self.set("model_version", "my_new_model_version")
        print(f'New data: {self.get("my_data")}')
        print(f'New model version: {self.get("model_version")}')

        print("fit() completed successfully.")
