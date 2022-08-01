import os.path
import time

import cv2
import math
import threading
import numpy as np
from openslide import open_slide

from code.utils import MAGNIFICATION_MAP, MAGNIFICATION_DICT, is_tile_mostly_background


def save_tiles(tile_list, tile_names, save_path):
    for tile, tile_name in zip(tile_list, tile_names):
        if is_tile_mostly_background(tile):
            continue
        y, x = str(tile_name[0]), str(tile_name[1])
        cv2.imwrite('{}/{}_{}.jpg'.format(save_path, y.zfill(4), x.zfill(4)), tile)


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
    def __init__(self, slide_path, tile_size, overlap, output_path):
        super(TileFactory).__init__()

        self.slide_id = ''.join(slide_path.split('\\')[-1].split('.')[:-1])
        self.output_path = os.path.join(output_path, self.slide_id)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        self.slide = open_slide(slide_path)
        self.tile_size = tile_size
        self.overlap = overlap
        self.magnification = int(self.slide.properties['openslide.objective-power'])

    def make_overview(self):
        slide_size = self.slide.level_dimensions[0]
        overview_scale = self.magnification / MAGNIFICATION_DICT['Overview']
        overview_size = (int(slide_size[0] / overview_scale), int(slide_size[1] / overview_scale))
        overview_image = self.slide.get_thumbnail(overview_size)
        overview_image.save('{}/Overview.jpg'.format(self.output_path))

    def make_tiles(self):
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

                    # saving tile images
                    slide_image = np.array(self.slide.read_region((0, 0), 0, level_slide_size))
                    slide_image = cv2.cvtColor(slide_image, cv2.COLOR_RGBA2BGR)

                    thread_queue = []
                    tiles_path = os.path.join(self.output_path, magnification_name)
                    if not os.path.exists(tiles_path):
                        os.makedirs(tiles_path)
                    for y, row_image in enumerate(np.split(slide_image, np.arange(self.tile_size, level_slide_size[0], self.tile_size), axis=0)):
                        row_tiles = []
                        tile_pos = []
                        for x, tile in enumerate(np.split(row_image, np.arange(self.tile_size, level_slide_size[0], self.tile_size), axis=1)):
                            row_tiles.append(tile)
                            tile_pos.append((y, x))

                        t = threading.Thread(target=save_tiles, args=(row_tiles, tile_pos, tiles_path))
                        t.start()
                        thread_queue.append(t)
            except Exception as e:
                print('slide: {}\tlevel: {} tiling failed'.format(self.slide_path, magnification))
                print(e)
                pass
        print(time.time() - start)

