import base64
import tempfile
import unittest
from pathlib import Path

from backend.repositories.database import (
    OperationalValidationError,
    create_operational_vendor,
    initialize_database,
)
from backend.services.vendors import (
    get_vendor_profile_photo,
    save_vendor_profile_photo,
)


class VendorProfilePhotoTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "vendor.db"
        initialize_database(self.database_path)
        vendor = create_operational_vendor(
            {"business_category": "food", "preferred_language": "en"},
            self.database_path,
        )
        self.vendor_id = vendor["vendor_id"]

    def tearDown(self):
        self.temp_directory.cleanup()

    @staticmethod
    def data_url(mime_type, image):
        encoded = base64.b64encode(image).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def test_profile_photo_is_saved_and_returned_as_a_data_url(self):
        photo = self.data_url("image/png", b"\x89PNG\r\n\x1a\nimage-data")

        saved = save_vendor_profile_photo(self.vendor_id, photo, self.database_path)
        loaded = get_vendor_profile_photo(self.vendor_id, self.database_path)

        self.assertEqual(saved, {"data_url": photo})
        self.assertEqual(loaded, {"data_url": photo})

    def test_profile_photo_rejects_mismatched_and_unsupported_image_types(self):
        with self.assertRaises(OperationalValidationError):
            save_vendor_profile_photo(
                self.vendor_id,
                self.data_url("image/png", b"\xff\xd8\xffjpeg-data"),
                self.database_path,
            )

        with self.assertRaises(OperationalValidationError):
            save_vendor_profile_photo(
                self.vendor_id,
                self.data_url("image/gif", b"GIF89a"),
                self.database_path,
            )

    def test_profile_photo_rejects_images_over_two_megabytes(self):
        oversized_png = b"\x89PNG\r\n\x1a\n" + b"x" * (2 * 1024 * 1024)

        with self.assertRaises(OperationalValidationError):
            save_vendor_profile_photo(
                self.vendor_id,
                self.data_url("image/png", oversized_png),
                self.database_path,
            )


if __name__ == "__main__":
    unittest.main()
