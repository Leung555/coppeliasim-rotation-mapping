# Train YOLO on your custom CoppeliaSim objects

This guide uses this project's `train.py`, `evaluate.py`, and `main.py`. Run all commands from `SIIT/rotation_mapping` with your virtual environment activated. Training happens in Python and does not require CoppeliaSim to be running once images are collected.

## Training and evaluation commands

Choose your augmentation profile explicitly:

| Option | Behavior |
|---|---|
| `--augmentation none` | Disable training transformations; retain resizing and normalization |
| `--augmentation mild` | Project's mild transformations (default when omitted) |
| `--augmentation default` | Ultralytics built-in augmentation defaults |

For training without augmentation, use the [no-augmentation workflow](#train-without-augmentation) below.

Run these commands from `SIIT/rotation_mapping` after activating your Python environment with the project dependencies. CoppeliaSim is not needed for training/evaluation.

```bash
# 1. Train Nano with mild augmentation.
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation mild --name objects_augmented --device cpu

# 2. Evaluate and save ground-truth/prediction comparisons.
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --split val --imgsz 640 --device cpu --preview --preview-conf 0.5 --match-iou 0.5

# 3. Run the robot with these weights (CoppeliaSim must be open and stopped).
python main.py --weights runs/objects_augmented/weights/best.pt
```

If training prints an incremented folder such as `objects_augmented2`, use that folder in both following commands. GPU users can replace `--device cpu` with `--device 0` for training and evaluation.

Open the training run's `results.png` for loss and metric curves, or `results.csv` for per-epoch values. Evaluation prints its actual `runs/evaluation*` folder; open `comparisons/*.png`, `metrics.json`, and the confusion-matrix plots there. Green preview predictions are correct, red are false positives, and orange ground-truth boxes are missed. Official metric values may differ from preview counts because their thresholds differ.

For a comparison against the original augmentation defaults:

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation default --name objects_baseline --device cpu
python evaluate.py --weights runs/objects_baseline/weights/best.pt --data dataset.yaml --imgsz 640 --device cpu --preview
```

Keep the dataset split fixed when comparing runs. `--split test` requires an existing labeled test set and a `test` entry in the YAML; it is not ready in the current dataset. A five-epoch pilot should use a separate `--name objects_pilot` so it stays distinct from full training.

## 1. Prepare the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The initial detector is YOLO11 Nano (`yolo11n.pt`), pretrained on COCO. We fine-tune its weights on your labeled object classes. The initial weights download requires internet access; afterward you can use the local weights. See the official [YOLO11 documentation](https://docs.ultralytics.com/models/yolo11).

## 2. Define the classes

Choose the types you need on the map. For example:

| Class ID | Name | Labeling rule |
|---|---|---|
| 0 | Cube | Every cube, regardless of color |
| 1 | Tree | Every tree, including its visible trunk and foliage |

These are examples, not classes already trained by this project. Use exactly the same IDs and names throughout labeling and the dataset YAML. If you want color-specific types, define separate classes consistently. Multiple cubes still share one class; the mapping code assigns separate landmark IDs by location.

## 3. Collect clean camera images

In `main.py`, edit `SETTINGS`:

```python
"save_frames": True,
"clahe": False,
"output_dir": "captures/scene_01",
```

Open CoppeliaSim, leave the simulation stopped, then run:

```bash
python main.py
```

The controller loads the configured `Demo_CV.ttt` and rotates the robot. The camera is `/body/visionSensor`. `--odom-only` skips the camera and does not collect images.

Use `rgb_*.png` for labeling. `frame_*.png` contains prediction overlays and should not be used for training. Images are saved before optional CLAHE. Keep CLAHE disabled for the initial training/inference workflow so image processing matches.

For another collection, change `output_dir` to `captures/scene_02` to avoid overwriting earlier files. Vary object positions, number of instances, viewing distance, partial occlusion, lighting, colors, and backgrounds. Include views with no target objects. Avoid keeping hundreds of nearly identical neighboring frames.

The program reloads the scene file on each run. To capture edited layouts, save them in a separate scene and change `scene_path`, or set `scene_path` to an empty string to use the currently open scene. Disable the image modification and periodic handling scripts from `../CV/cv_example`; the detector needs clean, aligned RGB/depth images.

Start with a few hundred varied labeled images as a pilot, then collect more based on the detector's failures. This is a starting point, not a guaranteed accuracy threshold.

## 4. Annotate bounding boxes

### Install and launch Label Studio

If Label Studio is already installed, activate the environment where you installed it and run `label-studio`. For a new installation, use these separate shell commands (the code block is Bash, not GraphQL):

```bash
# Create a virtual environment for the labeling tool, if needed.
python3 -m venv .venv-labelstudio
source .venv-labelstudio/bin/activate

# Install or upgrade Label Studio.
python -m pip install -U label-studio

# Start the labeling application.
label-studio
```

Open the local browser address printed by the command and follow the initial account setup. Keep the terminal running while labeling; Ctrl+C stops the server. This environment is for the labeling tool. Activate the project's `.venv` again before running training commands. Label Studio is optional and is not added to the robot runtime requirements. See the official [quick start](https://labelstud.io/guide/quick_start.html).

### Create an object detection project

1. Create a project, for example **CoppeliaSim Objects**.
2. Import your clean `rgb_*.png` images using file upload. Do not import annotated `frame_*.png` images. Give images unique filenames across scans before importing.
3. Choose the image object detection / bounding box labeling template, or use the following labeling configuration.
4. Replace the example class names with your actual object types before labeling.

```xml
<View>
  <Image name="image" value="$image"/>
  <RectangleLabels name="label" toName="image">
    <Label value="Cube" background="#E74C3C"/>
    <Label value="Tree" background="#2ECC71"/>
  </RectangleLabels>
</View>
```

This uses Label Studio's [bounding box template](https://labelstud.io/templates/image_bbox.html). Use ordinary axis-aligned rectangles for this project's detection model.

### Label and submit each image

For every image:

1. Draw a tight rectangle around each visible target object.
2. Assign its class ID. Label all target instances, not only the largest one.
3. Use a consistent rule for partially occluded objects; label the visible region consistently.
4. Review labels visually before exporting.

Select the class, draw its rectangle, then submit/save the annotation before moving to the next image. Finish and review all intended annotations before export. Mark reviewed images without target objects as completed with no boxes; do not treat unfinished images as background examples.

### Export to YOLO and check class IDs

1. Open the project's export menu and select **YOLO** for bounding boxes. If your version offers **YOLO with Images**, use it to include image files; otherwise keep the original images alongside the exported labels.
2. Download and extract the export archive to a separate staging folder. Keep it as a backup.
3. Inspect the exported class mapping, such as `classes.txt`, if present. The mapping in the export is the source of truth: do not assume the displayed label order guarantees your desired numeric IDs.
4. Set `names` in `dataset.yaml` to match the exported IDs exactly. For example, if the export maps cylinder to 0, use `0: cylinder` rather than the example's `0: cube`. If you deliberately change IDs, update every corresponding label file too.
5. Match each exported `.txt` file with its image by filename stem. Exported image names may differ from the originals; check the archive before copying or renaming files.
6. Use `prepare_dataset.py` to copy matching pairs into the splits described below. Exporting annotations does not automatically create this project's train/validation/test split.

Check that every box line contains exactly five fields: an integer class ID followed by four normalized coordinates. JSON export is not directly usable by `train.py`. Avoid segmentation or oriented-box export formats for this model. Label Studio documents YOLO support for `RectangleLabels` in its [export guide](https://labelstud.io/guide/export).

Each image has a matching text file with the same filename stem, such as `scene01_0001.png` and `scene01_0001.txt`. Each object occupies one line:

```text
class_id center_x center_y width height
```

Coordinates are normalized by image width/height, with values between 0 and 1. Class IDs are zero-based integers. This follows the official [Ultralytics detection dataset format](https://docs.ultralytics.com/datasets/detect).

Example: a 640×480 image has a cube box from `(160, 120)` to `(320, 360)`:

```text
0 0.375 0.5 0.25 0.5
```

Its center is `(240, 240)`, width is 160, height is 240. Divide x/width by 640 and y/height by 480. An image with no target objects can have an empty label file.

## 5. Split by scene and arrange the dataset

Label Studio's YOLO export is flat: `images/`, `labels/`, and optionally `classes.txt`. Prepare independent photos automatically:

```bash
python prepare_dataset.py --source /path/to/extracted-export --val-ratio 0.2
```

Output defaults to `dataset/` beside the script. It copies matching pairs, preserves source files, uses seed 42, and refuses to overwrite existing split folders. Missing labels cause an error; supply empty labels only for reviewed background images. `--output another_dataset` selects a different destination.

For the export containing cropped Cube/Tree video frames and separate screenshots:

```bash
python prepare_dataset.py --source /path/to/extracted-export --train-pattern '*_cropped.*' --val-pattern '*Screenshot*'
```

These patterns select 24 cropped training images and 17 validation screenshots in the current export, excluding 24 raw video variants. Both patterns must be provided, match images, and not overlap. Adapt them for other exports; the script does not infer recording groups. Review class coverage and empty labels after preparation.

If `classes.txt` exists, the script creates `dataset/dataset.yaml` with an absolute dataset path and the original class order. JSON syntax in that file is valid YAML. Use `--data dataset/dataset.yaml` in **both** `train.py` and `evaluate.py`; the existing project `dataset.yaml` is also compatible if its path and classes match. Without `classes.txt`, create a YAML using the template below. No test split is generated automatically.

An initial split can be approximately 70% training, 20% validation and 10% testing. Group images from the same layout/scan in one split. Adjacent frames from one rotation are similar; distributing them across splits can produce misleading evaluation results. Ensure classes are represented in each split where possible.

```text
dataset/
├── images/
│   ├── train/scene01_0001.png
│   ├── val/scene02_0001.png
│   └── test/scene03_0001.png
└── labels/
    ├── train/scene01_0001.txt
    ├── val/scene02_0001.txt
    └── test/scene03_0001.txt
```

Use unique names across collection sessions. Keep raw captures as a backup.

If no configuration was generated, copy the template:

```bash
cp dataset.example.yaml dataset.yaml
```

Edit `dataset.yaml`:

```yaml
path: /absolute/path/to/rotation_mapping/dataset
train: images/train
val: images/val
test: images/test
names:
  0: Cube
  1: Tree
```

Use your real absolute dataset root. The `test` entry is optional unless you run `--split test`. Check that all paths exist, IDs match the class list, boxes have positive sizes, and each image has the correct label filename.

## 6. Train

First use a short run to catch dataset problems:

```bash
python train.py --data dataset.yaml --epochs 5 --imgsz 640 --augmentation mild --name objects_pilot --device cpu
```

Then start a longer run:

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation mild --name objects_augmented --device cpu
```

For an available CUDA GPU with compatible PyTorch, replace `--device cpu` with `--device 0`. CPU training works but can be slow. The script uses Ultralytics defaults for options it does not expose, such as batch size. Training parameters are described in the official [training documentation](https://docs.ultralytics.com/modes/train).

| Option | Meaning |
|---|---|
| `--data` | Dataset YAML path |
| `--model` | Starting detector weights; default `yolo11n.pt` |
| `--epochs` | Maximum training passes; default 100 |
| `--imgsz` | Training input size; default 640 |
| `--device` | CPU or GPU index; default `cpu` |
| `--augmentation` | `none`, `mild` (default), or original library `default` profile |
| `--name` | Requested training folder name; default `objects_augmented` |

The script prints the actual output directory. Repeated runs may use `runs/objects_augmented2`, `runs/objects_augmented3`, etc. Record which dataset version and run produced your model.

Typical artifacts include `weights/best.pt`, `weights/last.pt`, training settings, curves and validation plots. Use `best.pt` for the robot. A five-epoch pilot is for checking the workflow, not establishing model quality.

## 7. Evaluate detection quality

Use the actual weights path printed by your training run:

```bash
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --device cpu
```

For the untouched test split:

```bash
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --split test --device cpu
```

Evaluation writes `metrics.json` and plots under the printed `runs/evaluation*` directory. Metrics include precision (how many predictions are correct), recall (how many labeled objects are found), and mAP (detection performance across confidence/overlap criteria). Inspect per-class results and prediction images as well as averages. See the official [validation documentation](https://docs.ultralytics.com/modes/val).

Use validation results to improve labels and collect missing views. Keep the test set separate from repeated tuning. Choose acceptance criteria based on your scene: missed small objects or confusing two classes may matter even when the average metric looks good.

## 8. Run with trained weights

```bash
python main.py --weights runs/objects_augmented/weights/best.pt
```

Alternatively set `SETTINGS["model"]` to the absolute `best.pt` path. The main program loads these weights and performs inference; it does not train during the robot loop. YOLO class names become the `type` values in `objects.json` and map labels.

Review annotated frames, then verify locations using known object placements. Detection evaluation does not measure map accuracy: depth selection, wheel measurements, slip and landmark merging can each affect the map independently.

## Improve the Cube and Tree detector

The initial 12-image dataset and 5-epoch run were workflow checks. The corrected dataset now contains 24 cropped training images and 17 validation screenshots with Cube and Tree classes; the latest inspected baseline completed 100 epochs. More epochs on these same images cannot replace diverse examples. The following sequence is a practical experiment plan for this project; accuracy targets and image counts depend on your scene.

### 1. Match training images to the robot camera

Collect clean `rgb_*.png` images from `/body/visionSensor`. If existing labels were made on desktop screenshots, replace or supplement them with sensor captures: window borders, toolbars and different viewpoints do not represent the input the robot receives.

Include Cube and Tree at different distances, left/right positions, viewing angles, apparent sizes and levels of occlusion. Include several objects together and scenes where objects are absent. Keep class representation reasonably balanced. Add confusing background shapes so the model learns when not to predict a target.

An initial collection goal can be a few hundred varied images across multiple layouts, with dozens of distinct examples for each class. These numbers are planning suggestions, not minimum requirements or guarantees. Choose varied frames rather than many duplicates from a stationary scene. Keep lighting and color changes plausible for deployment. Dataset quality and representative examples are emphasized in the official [training tips](https://docs.ultralytics.com/guides/model-training-tips).

### 2. Review labels before adding training time

Check every object instance, class assignment and box. Define whether a Tree box includes its trunk and foliage and whether a Bowl box includes its full visible rim/body, then follow the same rule across images. Do not label surrounding floor or desktop UI. Look for missing labels, oversized boxes and inconsistent handling of occlusion.

Keep the exported class mapping: `0: Cube`, `1: Tree`, unless your new export uses a different mapping. Match YAML names to the exported IDs. Include reviewed empty scenes with empty label files; unlabeled positive images are not valid negative examples.

### 3. Rebuild independent validation and test sets

Keep each scene layout or scan in one split. Repeated frames of the same object arrangement should not appear in both training and validation. Include both classes and difficult cases in held-out scenes. The current 17-image validation split is still small; review the empty annotations and collect more independent scenes.

As you add images, copy matching pairs into `dataset/images/{train,val,test}` and `dataset/labels/{train,val,test}`. New files placed only in the top-level export folders are not read by the current YAML. Add `test: images/test` only when a real labeled test split exists. Do not tune repeatedly on the final test set.

### 4. Train a baseline on the improved dataset

From the project directory:

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation mild --name objects_augmented --device cpu
```

Use `--device 0` if a compatible CUDA GPU is available. Start from the pretrained weights when comparing a new dataset against the old one. Use the actual run directory printed by training. Training can stop before the requested epoch limit under Ultralytics defaults; inspect the saved settings and curves. Supported options are explained in the official [training settings](https://docs.ultralytics.com/modes/train).

Evaluate and deploy that run's `best.pt`:

```bash
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml
python main.py --weights runs/objects_augmented/weights/best.pt
```

`objects_augmented` is the requested run name; repeated runs may append a number. Use the actual output directory printed by training. Record dataset version, starting model, epochs, image size, device, run path, per-class results and representative failures for each experiment.

### 5. Change one training choice at a time

| Observation | Next experiment | Tradeoff |
|---|---|---|
| Training and validation are still improving | Try more epochs, for example 150 | More compute; watch for overfitting |
| Training improves but held-out performance worsens | Add diversity, fix labels and inspect earlier/best weights | Extra epochs may make this worse |
| Small/distant objects are missed | Collect those views; then compare `--imgsz 960` | More memory/time; matching runtime resolution also matters |
| Nano misses objects despite good data | Compare `--model yolo11s.pt` with the same split | More training and inference cost |
| One class performs poorly | Collect and review examples of that class | A larger model alone may not resolve missing coverage |

Example comparisons, each producing a separate run:

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 960 --augmentation mild --name objects_nano_960 --device cpu
python train.py --data dataset.yaml --model yolo11s.pt --epochs 100 --imgsz 640 --augmentation mild --name objects_small --device cpu
```

The runtime currently uses Ultralytics' default prediction image size. A larger training size alone does not make runtime inference use that size; if you adopt a different size, explicitly configure and test the matching prediction/evaluation size in those scripts. Changing `--imgsz` does not add detail absent from low-resolution sensor images.

Our training script exposes model, epochs, image size and device. Batch size, learning rate and early-stopping patience use library defaults; augmentation can now be selected with `--augmentation none`, `--augmentation mild`, or `--augmentation default`. Do not pass unsupported flags such as `--batch` to this script. Advanced experiments require adding the option to the script or using the Ultralytics API. Keep augmentation representative of the simulated camera; it does not replace collecting missing views.

### 6. Inspect failures and collect targeted examples

Compare precision, recall, mAP, per-class plots and annotated validation images. Low precision suggests false positives; low recall suggests missed targets. Check which class, distance, occlusion or background causes the failure and add correctly labeled training examples of those conditions from new scenes. Retrain and evaluate on the same fixed validation set so comparisons remain meaningful.

In `main.py`, `confidence` defaults to 0.5. Lowering it temporarily to 0.25 can expose weak detections during diagnosis, but can increase false positives; it does not improve the trained weights. Restore or select the operating threshold using validation behavior. Enable `save_frames` to review detections and confirm that startup prints your custom weights and both classes.

A printed detection followed by “no valid depth” is a mapping issue. Check depth settings and whether the bounding-box centre hits the object. A zero-object map can result from detection or depth filtering; assess these separately from encoder odometry. Measure map error using known object placements after detection quality is acceptable.

## Troubleshooting

| Symptom | Check or action |
|---|---|
| Dataset images not found | Correct the YAML's absolute root and split paths |
| Labels missing or invalid | Check matching filename stems, normalized coordinates and class IDs |
| Cube/cylinder not detected with default weights | Train custom classes; COCO weights do not provide these generic shape classes |
| Excellent validation, poor new-scene performance | Split by scene, collect more varied scenes and check label consistency |
| Training loses small objects | Collect close and distant views, review tight boxes, consider increasing `--imgsz` |
| CUDA unavailable or out of memory | Use `--device cpu`; smaller image size can reduce memory use |
| New images replace earlier captures | Use a unique `output_dir` per scan |
| Correct detection but incorrect map location | Check encoder signs, wheel dimensions, sensor mounting, depth and merge radius |

The original project provides the workflow; your imported dataset and locally generated weights supply the custom detector. See the current dataset notes below.

## Current imported dataset

The active class mapping is `0: Cube`, `1: Tree`. Training uses 24 cropped video images (9 Cube, 15 Tree). Validation uses 17 separate screenshots with 6 Cube boxes, 5 Tree boxes and 7 empty annotations. Review empty labels to confirm no target was omitted. No test split is configured.

The original flat export stays in `dataset/images/` and `dataset/labels/`. The YAML reads the `train` and `val` subfolders, so new exported files must be placed in the appropriate split before training. See `dataset/README.md` and `dataset/split_report.json`.


## Visual comparison of labels and predictions

Use `python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --preview` to save one side-by-side comparison per validation image. For a labeled test set, add `--split test`. See [the README preview instructions](README.md#view-labels-beside-predictions) for the colors, confidence/IoU thresholds and output location. Inspect missed objects and false positives before collecting targeted training examples.

## Mild augmentation experiment

`train.py` now defaults to a mild augmentation profile. Images and bounding boxes are transformed together during training; original files and validation images are unchanged. This is a candidate recipe, not a proven improvement. The earlier baseline already used Ultralytics default augmentations.

| Setting | Mild profile | Purpose |
|---|---|---|
| HSV hue/saturation/value | 0.01 / 0.25 / 0.25 | Modest color and brightness variation |
| Rotation | ±5 degrees | Small camera tilt |
| Translation | 0.1 | Position shifts up to a fraction of image dimensions |
| Scale | 0.25 | Random scale gain roughly 0.75–1.25 |
| Horizontal flip | 50% probability | Left/right variation |
| Vertical flip, shear, perspective | Disabled | Keep upright scenes plausible |
| Mosaic | 30% probability | Combine scenes to vary composition |
| MixUp and copy-paste | Disabled | Keep the starting experiment simple |

Mosaic is disabled for the last `min(10, epochs // 5)` epochs. Other transformations stay active. Optional library transforms may still depend on installed packages; inspect the training log and saved `args.yaml`. See the official [augmentation guide](https://docs.ultralytics.com/guides/yolo-data-augmentation).

Run the experiment from the project directory:

```bash
python train.py --epochs 100 --augmentation mild --name objects_augmented --device cpu
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --preview
```

Repeated names may be incremented; use the output path printed by training. To compare against the original library defaults on the same fixed dataset:

```bash
python train.py --epochs 100 --augmentation default --name objects_baseline --device cpu
```

Compare both runs on the same validation split, image size and preview confidence. Review per-class misses, false positives and training batch plots (`train_batch*.jpg`). Keep the profile only if held-out performance improves. More augmentation cannot replace new camera views or independent recordings. No new training run is started automatically by this change.

## Train without augmentation

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation none --name objects_no_aug --device cpu
python evaluate.py --weights runs/objects_no_aug/weights/best.pt --data dataset.yaml --split val --imgsz 640 --device cpu --preview --preview-conf 0.5
```

`none` zeros color and geometric transformations, flipping, mosaic, MixUp and copy-paste, and disables the optional Albumentations wrapper in the training process. Required resizing/letterboxing and normalization remain. `default` still enables Ultralytics default augmentation; it does not mean augmentation is off. Use the actual run folder printed by training if its name increments.

For this run, inspect `runs/objects_no_aug/results.png` for loss/metric curves and `results.csv` for per-epoch values. Evaluation prints its comparison folder. To use the trained weights with the robot:

```bash
python main.py --weights runs/objects_no_aug/weights/best.pt
```

Compare `objects_no_aug` and `objects_augmented` using the same dataset split, epochs, image size and evaluation confidence. Keep the existing run artifacts; repeated run names may be incremented.
