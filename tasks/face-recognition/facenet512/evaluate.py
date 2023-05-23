#!/usr/bin/env python3

# SPDX-License-Identifier: MIT
# Copyright 2022-2023 NXP

import cv2
import os
import numpy as np
from glob import glob
import tensorflow as tf
import tqdm
from deepface.basemodels.Facenet512 import loadModel

THRESHOLD = 0.6

# download and extract http://vis-www.cs.umass.edu/lfw/lfw-deepfunneled.tgz
LFW_DIR = "lfw-deepfunneled"

# download http://vis-www.cs.umass.edu/lfw/pairsDevTest.txt
LFW_PAIRS_FILE = "pairsDevTest.txt"

# file generated by recipe.sh
TFLITE_MODEL_FILE = "facenet512_uint8.tflite"


def cosine_similarity(a, b):
    return 1 - np.dot(a, b) / (np.linalg.norm(a)*np.linalg.norm(b))


def load_img(filename):
    img = cv2.imread(filename, 1)
    img = img[45:-45, 45:-45]

    img = np.array(img, dtype=np.uint8)
    img = img[None, ...]

    return img


interpreter = tf.lite.Interpreter(TFLITE_MODEL_FILE)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()


model_keras = loadModel()

with open(LFW_PAIRS_FILE, 'r') as f:
    pairs = f.readlines()[1:]
    pairs = [p.strip().split("\t") for p in pairs]

image_filenames = set()
for line in pairs[:500]:
    image_filenames.add(os.sep.join([LFW_DIR, line[0],
                                    f"{line[0]}_{int(line[1]):04d}.jpg"]))
    image_filenames.add(os.sep.join([LFW_DIR, line[0],
                                    f"{line[0]}_{int(line[2]):04d}.jpg"]))

for line in pairs[500:]:
    image_filenames.add(os.sep.join([LFW_DIR, line[0],
                                    f"{line[0]}_{int(line[1]):04d}.jpg"]))
    image_filenames.add(os.sep.join([LFW_DIR, line[2],
                                    f"{line[2]}_{int(line[3]):04d}.jpg"]))

feature_vectors = dict()
feature_vectors_keras = dict()
for f in tqdm.tqdm(image_filenames, desc="Running inferences"):

    img = load_img(f)

    interpreter.set_tensor(input_details[0]['index'], img)
    interpreter.invoke()
    out = interpreter.get_tensor(output_details[0]['index'])
    feature_vectors[f] = out[0, ...]
    feature_vectors_keras[f] = model_keras(img / 255.0)[0, ...]


n_correct, n_correct_keras = 0, 0

# evaluate same person pairs
for line in pairs[:500]:
    f1 = os.sep.join([LFW_DIR, line[0], f"{line[0]}_{int(line[1]):04d}.jpg"])
    f2 = os.sep.join([LFW_DIR, line[0], f"{line[0]}_{int(line[2]):04d}.jpg"])

    result = cosine_similarity(feature_vectors[f1], feature_vectors[f2])
    n_correct += 1 if result < THRESHOLD else 0

    result_keras = cosine_similarity(feature_vectors_keras[f1],
                                     feature_vectors_keras[f2])
    n_correct_keras += 1 if result_keras < THRESHOLD else 0

# evaluate different person pairs
for line in pairs[500:]:
    f1 = os.sep.join([LFW_DIR, line[0], f"{line[0]}_{int(line[1]):04d}.jpg"])
    f2 = os.sep.join([LFW_DIR, line[2], f"{line[2]}_{int(line[3]):04d}.jpg"])

    result = cosine_similarity(feature_vectors[f1], feature_vectors[f2])
    n_correct += 1 if result > THRESHOLD else 0

    result_keras = cosine_similarity(feature_vectors_keras[f1],
                                     feature_vectors_keras[f2])
    n_correct_keras += 1 if result_keras > THRESHOLD else 0


print("Quantized model accuracy:", n_correct/1000.0)
print("Floating-point model accuracy:", n_correct_keras/1000.0)
