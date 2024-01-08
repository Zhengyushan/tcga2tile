import os.path
import time
import traceback
from concurrent.futures import ProcessPoolExecutor

import cv2
import math
import threading
import numpy as np
from openslide import open_slide

from code.utils import MAGNIFICATION_MAP, MAGNIFICATION_DICT, is_tile_mostly_background, is_tile_size_too_small


class GridsCropWorker:
    def __init__(self, slide_path, width, height, target_tile_size, overlap, level, scale, save_path):
        self.slide_path = slide_path
        self.width = width
        self.height = height
        self.target_tile_size = target_tile_size
        self.overlap = overlap
        self.level = level

        self.save_path = save_path
        self.scale = scale

    def crop_tiles(self, grids):
        slide = open_slide(self.slide_path)
        crop_num = 0
        for x, y in grids:
            try:
                tile = slide.read_region((x * self.scale, y * self.scale), level=self.level, size=(self.width, self.height))
            except Exception as e:
                traceback.print_exc()
                print('Tile in x:{} y:{} crop failed.')
                continue

            # Check if the size of the patch is consistent with the target size. If not, resize it to the target size.
            if self.height != self.target_tile_size:
                tile = tile.resize((self.target_tile_size, self.target_tile_size))

            # Check if the patch is a background area. If it is, do not save it.
            if is_tile_mostly_background(tile):
                crop_num += 1
                continue

            tile = tile.convert('RGB')
            # Check if the size of the patch file is too small. If it is, do not save it.
            if is_tile_size_too_small(tile):
                crop_num += 1
                continue

            # Save the patch using a row and column naming method.
            y_pos = round(y / self.height)
            x_pos = round(x / self.width)
            tile.save('{}/{}_{}.jpg'.format(self.save_path, str(y_pos).zfill(4), str(x_pos).zfill(4)))
            crop_num += 1
        return crop_num


def save_level_file(file_name, slide_id, level_tiles_num, magnification, size, tile_size):
    cols, rows = level_tiles_num
    with open(file_name, 'w+') as info_file:
        info_file.write('slideId: {}\n'.format(slide_id))
        info_file.write('Objective: {}\n'.format(magnification))
        info_file.write('Patch_size: {}\n'.format(tile_size))
        info_file.write('rows: {}\n'.format(rows))
        info_file.write('cols: {}\n'.format(cols))
        info_file.write('height: {}\n'.format(size[1]))
        info_file.write('width: {}\n'.format(size[0]))


# Find the closest previous level to the target level.
def find_closest_magnification(magnification_map, target_magnification):
    closest_magnification = None
    min_difference = float('inf')

    for magnification in magnification_map.keys():
        difference = magnification - target_magnification
        if difference > 0 and difference < min_difference:
            closest_magnification = magnification
            min_difference = difference

    return closest_magnification


class TileFactory(object):
    def __init__(self, slide_path, tile_size, overlap, output_path, num_workers):
        super(TileFactory).__init__()
        self.slide_path = slide_path
        self.slide_id = ''.join(slide_path.split('/')[-1].split('.svs')[:-1])
        self.output_path = os.path.join(output_path, self.slide_id)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        self.slide = open_slide(slide_path)
        self.tile_size = int(tile_size)
        self.overlap = int(overlap)

        if 'openslide.objective-power' not in self.slide.properties.keys():
            raise KeyError

        self.magnification = int(self.slide.properties['openslide.objective-power'])
        self.num_workers = num_workers
        self.WSI_DOWNSAMPLE_MAP = {}

        # Create a DOWNSAMPLE_MAP for the WSI.
        for level in range(self.slide.level_count):
            scale = round(self.slide.level_downsamples[level])
            magnification = self.magnification / scale
            self.WSI_DOWNSAMPLE_MAP[magnification] = level

    def make_overview(self):
        slide_size = self.slide.level_dimensions[0]
        overview_scale = self.magnification / MAGNIFICATION_DICT['Overview']
        overview_size = (int(slide_size[0] / overview_scale), int(slide_size[1] / overview_scale))
        overview_image = self.slide.get_thumbnail(overview_size)
        overview_image.save('{}/Overview.jpg'.format(self.output_path))

    def make_tiles(self):
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            start = time.time()
            # Crop the patch according to the MAGNIFICATION_MAP.
            for magnification in MAGNIFICATION_MAP:
                # When the WSI has the level that needs to be cropped.
                if magnification in self.WSI_DOWNSAMPLE_MAP:
                    level = self.WSI_DOWNSAMPLE_MAP[magnification]
                    scale = round(self.slide.level_downsamples[level])
                    tile_size = self.tile_size
                    try:
                        magnification_name = MAGNIFICATION_MAP[magnification]
                        level_slide_size = self.slide.level_dimensions[level]
                        level_tiles_num = [int(level_slide_size[0] / tile_size),
                                           int(level_slide_size[1] / tile_size)]
                        save_level_file('{}/{}.txt'.format(self.output_path, magnification_name), self.slide_id,
                                        level_tiles_num, magnification, level_slide_size, tile_size)

                        crop_step = tile_size - self.overlap
                        xs = np.arange(0, level_slide_size[0] - tile_size, crop_step)
                        ys = np.arange(0, level_slide_size[1] - tile_size, crop_step)

                        x_grids, y_grids = np.meshgrid(xs, ys)
                        grids = np.stack([x_grids.reshape(-1), y_grids.reshape(-1)], 1)

                        save_path = os.path.join(self.output_path, magnification_name)
                        if not os.path.exists(save_path):
                            os.makedirs(save_path)

                        grid_crop_worker = GridsCropWorker(self.slide_path, tile_size, tile_size, self.tile_size,
                                                           self.overlap, level, scale, save_path)
                        crop_num = list(executor.map(grid_crop_worker.crop_tiles,
                                                     np.array_split(grids, self.num_workers)))
                        crop_num = sum(crop_num)
                        if crop_num != len(grids):
                            print('slide: {} cropped incompletely')
                    except Exception as e:
                        traceback.print_exc()
                        print('slide: {} level: {}x tiling failed'.format(self.slide_path, magnification))
                        pass
                # When the WSI does not have the level that needs to be cropped.
                else:
                    # When the level to be cropped is larger than the level of the base map, skip it directly.
                    if magnification > self.magnification:
                        continue
                    # Find the closest previous level to the target level in the WSI.
                    upsample_magnification = find_closest_magnification(self.WSI_DOWNSAMPLE_MAP, magnification)
                    level = self.WSI_DOWNSAMPLE_MAP[upsample_magnification]
                    scale_factor = int(upsample_magnification / magnification)
                    tile_size = self.tile_size * scale_factor
                    scale = round(self.slide.level_downsamples[level])
                    try:
                        magnification_name = MAGNIFICATION_MAP[magnification]
                        level_slide_size = self.slide.level_dimensions[level]
                        level_tiles_num = [int(level_slide_size[0] / tile_size),
                                           int(level_slide_size[1] / tile_size)]
                        save_level_file('{}/{}.txt'.format(self.output_path, magnification_name), self.slide_id,
                                        level_tiles_num, magnification, level_slide_size, tile_size)

                        crop_step = tile_size - self.overlap
                        xs = np.arange(0, level_slide_size[0] - tile_size, crop_step)
                        ys = np.arange(0, level_slide_size[1] - tile_size, crop_step)

                        x_grids, y_grids = np.meshgrid(xs, ys)
                        grids = np.stack([x_grids.reshape(-1), y_grids.reshape(-1)], 1)

                        save_path = os.path.join(self.output_path, magnification_name)
                        if not os.path.exists(save_path):
                            os.makedirs(save_path)

                        grid_crop_worker = GridsCropWorker(self.slide_path, tile_size, tile_size, self.tile_size,
                                                           self.overlap, level, scale, save_path)
                        crop_num = list(executor.map(grid_crop_worker.crop_tiles,
                                                     np.array_split(grids, self.num_workers)))
                        crop_num = sum(crop_num)
                        if crop_num != len(grids):
                            print('slide: {} cropped incompletely')
                    except Exception as e:
                        traceback.print_exc()
                        print('slide: {} level: {}x tiling failed'.format(self.slide_path, magnification))
                        pass
            print(time.time() - start)