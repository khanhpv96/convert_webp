# Image Converter Repository

This repository contains two scripts for converting image files to the WebP format, aimed at optimizing image storage and web delivery. The Python script is designed to run on a local machine, while the PHP script is intended for integration with WordPress websites.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Usage](#usage)
  - [Python Script (`convert_webp.py`)](#python-script-convert_webppy)
  - [PHP Script (`convert-to-webp.php`)](#php-script-convert-to-webpphp)
- [License](#license)

## Features

- Converts images (JPG, JPEG, PNG) to WebP format.
- Preserves transparency for PNG files.
- Batch processing for all images in a directory (Python script).
- Deletes the original image after successful conversion (Python script).
- Designed for seamless WordPress integration (PHP script).

## Requirements

### Python Script (`convert_webp.py`)
- Python 3.x
- [Pillow](https://pypi.org/project/Pillow/) library

### PHP Script (`convert-to-webp.php`)
- PHP 7.0 or higher
- GD library enabled in your PHP environment
- WordPress website for deployment

## Usage

### Python Script (`convert_webp.py`)

This script processes all image files within the `uploads` directory on your local machine. It converts eligible images to WebP and deletes the original files upon successful conversion.

#### Steps:
1. Install dependencies:
   ```bash
   pip install Pillow
   ```
2. Place your images in the `uploads` directory (located in the same folder as the script).
3. Run the script:
   ```bash
   python convert_webp.py
   ```
4. Check the console output for the conversion report.

#### Configuration:
- **Compression Quality**: Adjust the `quality` variable in the script (default is 80).

---

### PHP Script (`convert-to-webp.php`)

This script is intended for use on a WordPress website. It replaces old image files with their WebP equivalents after conversion.

#### Deployment and Usage:
1. Upload the `convert-to-webp.php` script to your WordPress root directory.
   - File URL: `<your-domain>/convert-to-webp.php`
2. Call the script by accessing it via your browser or server:
   ```
   https://<your-domain>/convert-to-webp.php
   ```
3. The script will process images in the WordPress `uploads` folder, convert them to WebP format, and replace the original images with the newly converted ones.

#### Configuration:
- Modify the `$quality` parameter in the script (default is 80) to adjust compression quality.
- Ensure the PHP script has permission to access and modify files in the `uploads` directory.

## License

This project is licensed under the MIT License.
