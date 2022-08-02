# tcga2tile

This code is used to convert TCGA histopathology slide into image tiles.

## Preparation

You may need to download the slides from TCGA before using the scripts in this repository.

Download code please refer to [https://github.com/MarvinLer/tcga_segmentation](https://github.com/MarvinLer/tcga_segmentation)

## Data format

```
TCGA-Lung                                 # The directory of the data.
├─ TCGA-63-5128-01A-01-BS1.2635b7d6-bf3d-40b0-89c0-419f0e4d9fb2   
│  ├─ Large                               # The directory of image tiles in Level 0 (40X lens).
│  │  ├─ 0000_0000.jpg                    # The image tile in Row 0 and Column 0.
│  │  ├─ 0000_0001.jpg                    # The image tile in Row 0 and Column 1.
│  │  └─ ...
│  ├─ Medium                              # The directory of image tiles in Level 1 (20X lens).
│  │  ├─ 0000_0000.jpg
│  │  ├─ 0000_0001.jpg
│  │  └─ ...
│  ├─ Small                               # The directory of image tiles in Level 2 (10X lens).
│  │  ├─ 0000_0000.jpg
│  │  ├─ 0000_0001.jpg
│  │  └─ ...
│  ├─ Overview                            # The directory of image tiles in Level 3 (5X lens).
│  │  ├─ 0000_0000.jpg
│  │  ├─ 0000_0001.jpg
│  │  └─ ...
│  ├─ Overview.jpg                        # The thumbnail of the WSI in Level 3.      
│  ├─ Large.txt                           # The information of the WSI in Level 0.   
│  ├─ Medium.txt                          # The information of the WSI in Level 1.   
│  └─ Small.txt                           # The information of the WSI in Level 2.  
├─ TCGA-77-7138-01A-02-BS2.7ebacc9b-2f09-47d1-b3f5-01230b15b6b2
└─ ...
```

## Convert slide to tiles

```
python main.py --tile-size 512 --overlap 0 --slide-file <path to save slide> <path to save tiles>
```



