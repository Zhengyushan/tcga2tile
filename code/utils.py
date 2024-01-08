import os
import imageio
import logging
import numpy as np
import cv2
import io


# max number of processes for parallelism
N_PROCESSES = 5

MAGNIFICATION_DICT = {
    'Large': 40,
    'Medium': 20,
    'Small': 10,
    'Overview': 5,
    'Minimum': 2.5
}

MAGNIFICATION_MAP = {
    40: 'Large',
    20: 'Medium',
    10: 'Small',
    5: 'Overview'
}


def infer_class_from_slide_id(slide_id):
    # https://docs.gdc.cancer.gov/Encyclopedia/pages/TCGA_Barcode/
    sample_code_and_vial = slide_id.split('-')[3]
    sample_code = int(sample_code_and_vial[:2])
    assert 0 <= sample_code < 100

    # Return 1 for tumor type, 0 otherwise:
    # https://gdc.cancer.gov/resources-tcga-users/tcga-code-tables/sample-type-codes
    return int(sample_code < 10)


def is_tile_size_too_small(image, file_size_threshold=5):
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format('JPEG'))
    img_byte_arr = img_byte_arr.getvalue()
    img_file_size = len(img_byte_arr) / 1024

    return img_file_size < file_size_threshold


def is_tile_mostly_background(image, background_pixel_value=220, background_threshold=0.75):
    image = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGBA2BGR)
    channel_above_threshold = image > background_pixel_value
    pixel_above_threshold = np.prod(channel_above_threshold, axis=-1)
    percent_background_pixels = np.sum(pixel_above_threshold) / (image.shape[0] * image.shape[1])

    return percent_background_pixels > background_threshold


def get_logger(filename_handler, verbose=False):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # file handler
        filepath = os.path.join('logs', filename_handler)
        if not os.path.exists(os.path.dirname(os.path.abspath(filepath))):
            os.makedirs(os.path.dirname(os.path.abspath(filepath)))
        fh = logging.FileHandler(filepath)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                      datefmt='%d/%m/%Y %I:%M:%S %p')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG if verbose else logging.INFO)
        formatter = logging.Formatter('%(levelname)s     %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    return logger


def list_slides_in_folder(input_folder, with_supfolder=False):
    slides_format = ('.svs', '.vms', '.vmu', '.ndpi', '.scn', '.mrxs', '.tif', '.tiff', '.bif')

    all_files_folders = list(map(lambda f: os.path.join(input_folder, f), os.listdir(input_folder)))
    if with_supfolder:
        only_folders = list(filter(lambda f: not os.path.isfile(f), all_files_folders))
        # list all slides within each folder of the input folder
        all_slides = [list(map(lambda f: os.path.join(folder, f),
                               list(filter(lambda f: f.endswith(slides_format), os.listdir(folder)))))
                      for folder in only_folders]
        # flatten
        all_slides = [slide for slide_group in all_slides for slide in slide_group]
        return all_slides

    only_files = list(filter(os.path.isfile, all_files_folders))
    return list(filter(lambda f: f.endswith(slides_format), only_files))
