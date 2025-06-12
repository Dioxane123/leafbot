import base64
def img_to_b64(img_path: str) -> str:
    """
    Convert an image file to a base64 encoded string.

    :param img_path: Path to the image file.
    :return: Base64 encoded string of the image.
    """
    with open(img_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return "base64://" + encoded_string