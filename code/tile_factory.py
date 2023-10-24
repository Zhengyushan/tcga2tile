import os.path
import time
import traceback
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from openslide import open_slide

from code.utils import MAGNIFICATION_MAP, MAGNIFICATION_DICT, is_tile_mostly_background


class GridsCropWorker:
    def __init__(self, slide_path, width, height, overlap, level, save_path):
        self.slide_path = slide_path
        self.width = width
        self.height = height
        self.overlap = overlap
        self.level = level

        self.save_path = save_path

    def crop_tiles(self, grids):
        slide = open_slide(self.slide_path)
        crop_num = 0
        for x, y in grids:
            try:
                tile = slide.read_region((x, y), level=self.level, size=(self.width, self.height))
            except Exception as e:
                traceback.print_exc()
                print('Tile in x:{} y:{} crop failed.')
                continue
            tile = tile.convert('RGB')
            tile.save('{}/{}_{}.jpg'.format(self.save_path, str(y).zfill(4), str(x).zfill(4)))
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


class TileFactory(object):
    def __init__(self, slide_path, tile_size, overlap, output_path, num_workers):
        super(TileFactory).__init__()
        self.slide_path = slide_path
        self.slide_id = ''.join(slide_path.split('\\')[-1].split('.')[:-1])
        self.output_path = os.path.join(output_path, self.slide_id)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        self.slide = open_slide(slide_path)
        self.tile_size = int(tile_size)
        self.overlap = int(overlap)

        self.mpp = 10000 / float(self.slide.properties['tiff.XResolution'])

        self.magnification = 40
        # self.magnification = int(self.slide.properties['openslide.objective-power'])
        self.num_workers = num_workers

    def make_overview(self):
        slide_size = self.slide.level_dimensions[0]
        overview_scale = self.magnification / MAGNIFICATION_DICT['Overview']
        overview_size = (int(slide_size[0] / overview_scale), int(slide_size[1] / overview_scale))
        overview_image = self.slide.get_thumbnail(overview_size)
        overview_image.save('{}/Overview.jpg'.format(self.output_path))

    def make_tiles(self):
        with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
            start = time.time()
            for level in range(self.slide.level_count):
                magnification = self.magnification / (2 ** level)
                try:
                    if magnification in MAGNIFICATION_MAP:
                        magnification_name = MAGNIFICATION_MAP[magnification]
                        level_slide_size = self.slide.level_dimensions[level]

                        # saving level information file
                        level_tiles_num = [int(level_slide_size[0]/self.tile_size), int(level_slide_size[1]/self.tile_size)]
                        save_level_file('{}/{}.txt'.format(self.output_path, magnification_name), self.slide_id,
                                        level_tiles_num, magnification, level_slide_size, self.tile_size)

                        crop_step = self.tile_size - self.overlap
                        xs = np.arange(0, level_slide_size[0] - self.tile_size, crop_step)
                        ys = np.arange(0, level_slide_size[1] - self.tile_size, crop_step)

                        x_grids, y_grids = np.meshgrid(xs, ys)
                        grids = np.stack([x_grids.reshape(-1), y_grids.reshape(-1)], 1)

                        save_path = os.path.join(self.output_path, magnification_name)
                        if not os.path.exists(save_path):
                            os.makedirs(save_path)
                        grid_crop_worker = GridsCropWorker(self.slide_path, self.tile_size, self.tile_size, self.overlap, level, save_path)
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

