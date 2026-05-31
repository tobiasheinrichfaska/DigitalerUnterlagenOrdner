from PIL import Image


class PreviewPage:
    """A rendered preview page: a PIL image + its page index.

    Headless (no Tk). The Tk view builds its own ``ImageTk.PhotoImage`` from
    ``pil_image`` when drawing on the canvas; a web/React UI uses the PNG form
    from services.render instead.
    """

    def __init__(self, pil_image: Image.Image, page_index: int):
        self.pil_image = pil_image
        self.page_index = page_index
