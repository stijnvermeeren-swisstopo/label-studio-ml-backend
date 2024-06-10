"""Tesseract OCR model for Label Studio."""

import io
import logging
import os
import re
from pathlib import Path

import boto3
import fitz
from PIL import Image

from label_studio_ml.model import LabelStudioMLBase

logger = logging.getLogger(__name__)
global OCR_config
OCR_config = "--psm 6 -l chi_sim+eng+deu"

LABEL_STUDIO_ACCESS_TOKEN = os.environ.get("LABEL_STUDIO_ACCESS_TOKEN")
LABEL_STUDIO_HOST = os.environ.get("LABEL_STUDIO_HOST")

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.environ.get("AWS_SESSION_TOKEN")
AWS_ENDPOINT = os.environ.get("AWS_ENDPOINT")

S3_TARGET = boto3.resource(
    "s3",
    endpoint_url=AWS_ENDPOINT,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN,
    config=boto3.session.Config(signature_version="s3v4"),
    verify=False,
)


class BBOXOCR(LabelStudioMLBase):
    """Model for OCR from text assigned to pdfs."""

    def load_image(self, img_path_url, task_id):
        # load an s3 image, this is very basic demonstration code
        # you may need to modify to fit your own needs
        if img_path_url.startswith("s3:"):
            bucket_name = img_path_url.split("/")[2]
            key = "/".join(img_path_url.split("/")[3:])

            obj = S3_TARGET.Object(bucket_name, key).get()
            data = obj["Body"].read()
            image = Image.open(io.BytesIO(data))
            return image
        else:
            # some hack to make image loading work:
            file_name = img_path_url.split("/")[-1]
            filepath = Path("/data/test_png/") / file_name

            # filepath = self.get_local_path(
            #     img_path_url,
            #     ls_access_token=LABEL_STUDIO_ACCESS_TOKEN,
            #     ls_host=LABEL_STUDIO_HOST,
            #     task_id=task_id
            # )
            return Image.open(filepath)

    def predict(self, tasks, **kwargs):
        # extract task metadata: labels, from_name, to_name and other
        from_name, to_name, value = self.label_interface.get_first_tag_occurence("TextArea", "Image")
        task = tasks[0]
        print(task["data"][value])
        pdf_path_url = task["data"][value].split("_")[:-1]
        page_number = task["data"][value].split("_")[-1]
        page_number = int(page_number.split(".")[0])
        pdf_path_url = "".join(pdf_path_url) + ".pdf"
        pdf_name = pdf_path_url.split("/")[-1]
        pdf_path = Path("/data/validation/") / pdf_name

        context = kwargs.get("context")
        if context:
            if not context["result"]:
                return []
            document = fitz.open(pdf_path)
            page = document[page_number]

            result = context.get("result")[-1]
            meta = self._extract_meta({**task, **result})
            x = meta["x"] * meta["original_width"] / 100
            y = meta["y"] * meta["original_height"] / 100
            w = meta["width"] * meta["original_width"] / 100
            h = meta["height"] * meta["original_height"] / 100

            page_x = x * page.rect.width / meta["original_width"]
            page_y = y * page.rect.height / meta["original_height"]
            page_w = w * page.rect.width / meta["original_width"]
            page_h = h * page.rect.height / meta["original_height"]
            result_text = fitz.utils.get_text(page, "text", clip=[page_x, page_y, page_x + page_w, page_y + page_h])
            result_text = result_text.replace("\n", " ")

            # check if the label is Depth Interval; if so, extract the depth interval values
            for result in context["result"]:
                if result["from_name"] == "label":  # noqa: SIM102
                    if result["value"]["labels"] == ["Depth Interval"]:
                        result_text = extract_depth_interval(result_text)

            temp = {
                "original_width": meta["original_width"],
                "original_height": meta["original_height"],
                "image_rotation": 0,
                "value": {
                    "x": x / meta["original_width"] * 100,
                    "y": y / meta["original_height"] * 100,
                    "width": w / meta["original_width"] * 100,
                    "height": h / meta["original_height"] * 100,
                    "rotation": 0,
                    "text": [result_text],
                },
                "id": meta["id"],
                "from_name": from_name,
                "to_name": meta["to_name"],
                "type": "textarea",
                "origin": "manual",
            }
            return [{"result": [temp, result], "score": 0}]
        else:
            return []

    @staticmethod
    def _extract_meta(task):
        meta = dict()
        if task:
            meta["id"] = task["id"]
            meta["from_name"] = task["from_name"]
            meta["to_name"] = task["to_name"]
            meta["type"] = task["type"]
            meta["x"] = task["value"]["x"]
            meta["y"] = task["value"]["y"]
            meta["width"] = task["value"]["width"]
            meta["height"] = task["value"]["height"]
            meta["original_width"] = task["original_width"]
            meta["original_height"] = task["original_height"]
        return meta


def extract_depth_interval(result_text: str) -> str:
    """Extract depth interval from OCR result.

    Args:
        result_text (str): The OCR result text.

    Returns:
        str: The extracted depth interval.
    """
    numbers = get_numbers_from_string(result_text)
    if len(numbers) == 1:
        return f"start: 0 end: {numbers[0]}"
    if len(numbers) >= 2:
        return f"start: {numbers[0]} end: {numbers[-1]}"
    else:
        print(f"No number was detected in the bounding box: {result_text}. The recognized numbers are {numbers}.")
        return "start: end: "


def get_numbers_from_string(string: str) -> float:
    """Extract the first number from a string.

    Supports various notation of numbers including scientific notation.

    Args:
        string (str): The string to extract the number from.

    Returns:
        float: The extracted number.
    """
    numbers = re.findall("-?([0-9]+([\.,][0-9]+)?)", string)
    numbers = [number[0].replace(",", ".") for number in numbers]
    numbers = [abs(float(number)) for number in numbers]
    return numbers
