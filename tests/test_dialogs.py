from safebox.ui.branding import SAFEBOX_LOGIN_LOGO_PATH
from safebox.ui.dialogs import CATEGORIES, AccountDialog, VaultOpenDialog, VaultOpenMode


def _corner_pixels_are_transparent(path) -> bool:
    from PIL import Image

    image = Image.open(path).convert("RGBA")
    corners = (
        image.getpixel((0, 0)),
        image.getpixel((image.width - 1, 0)),
        image.getpixel((0, image.height - 1)),
        image.getpixel((image.width - 1, image.height - 1)),
    )
    return all(pixel[3] == 0 for pixel in corners)


def _edge_background_is_transparent(path) -> bool:
    from PIL import Image

    image = Image.open(path).convert("RGBA")
    sample_points = (
        (image.width // 2, 8),
        (8, image.height // 2),
        (image.width - 9, image.height // 2),
        (image.width // 2, image.height - 9),
    )
    return all(image.getpixel(point)[3] == 0 for point in sample_points)


def test_account_categories_include_email(qt_app) -> None:
    dialog = AccountDialog()

    try:
        assert "邮箱" in CATEGORIES
        category_items = [
            dialog.category.itemText(index) for index in range(dialog.category.count())
        ]
        assert "邮箱" in category_items
    finally:
        dialog.close()


def test_vault_register_mode_makes_register_the_primary_action(qt_app) -> None:
    dialog = VaultOpenDialog()

    try:
        dialog._toggle_mode()

        assert dialog.mode == VaultOpenMode.REGISTER
        assert dialog.open_button.objectName() == "SubtleButton"
        assert dialog.register_button.objectName() == "PrimaryButton"
    finally:
        dialog.close()


def test_vault_login_uses_project_bundled_brand_mark(qt_app) -> None:
    dialog = VaultOpenDialog()

    try:
        assert SAFEBOX_LOGIN_LOGO_PATH.is_file()
        assert _corner_pixels_are_transparent(SAFEBOX_LOGIN_LOGO_PATH)
        assert _edge_background_is_transparent(SAFEBOX_LOGIN_LOGO_PATH)
        assert dialog.brand_mark.pixmap() is not None
        assert str(SAFEBOX_LOGIN_LOGO_PATH).startswith(str(SAFEBOX_LOGIN_LOGO_PATH.parents[1]))
    finally:
        dialog.close()
