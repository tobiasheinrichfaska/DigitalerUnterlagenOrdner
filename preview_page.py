from PIL import Image, ImageTk

class PreviewPage:
    def __init__(self, pil_image: Image.Image, page_index: int):
        self.pil_image = pil_image
        self.tk_image = None
        self.page_index = page_index

    def get_tk_image(self) -> ImageTk.PhotoImage:
        if self.tk_image is None:
            self.tk_image = ImageTk.PhotoImage(self.pil_image)
        return self.tk_image
