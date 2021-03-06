#!/usr/bin/env python

import time

from utils.data_loader import MRI_Loader
from utils.callbacks import Metrics_Conversion_Risk, LR_Plateau
from utils.preprocess import Stratified_KFolds_Generator, Train_Test_Split, One_Hot_Encode
from utils.models import MudNet
from utils.plot_metrics import plot_metrics

from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import EarlyStopping

from sklearn.utils.class_weight import compute_class_weight

import numpy as np
import pandas as pd
import tensorflow as tf

# Hide GPU devices with limited memory
physical_devices = tf.config.list_physical_devices('GPU')        
for gpu in physical_devices:
  # GPU memory growth for dynamic memory allocation                                           
  tf.config.experimental.set_memory_growth(gpu, True)

# Data parameters
iterations = 1
target_width = 197
target_height = 233
target_depth = 189
clinical_features = 14
features_shape_dict = {'mri':(target_width,target_height,target_depth,1), 'clinical':clinical_features}
output_class_dict = {'conversion':1, 'risk':3}
limit_size = None
test_size = 0.2

# Model parameters
epochs = 100
learning_rate = 0.047
batch_size = 20
prefetch_size = batch_size
dropout_rate = {'mri':0.06,'clinical':0.17}
regularizer = {'mri':0.028,'clinical':0.028,'fc':0.028}

# Load MRI data
mri_loader = MRI_Loader(target_shape=(target_width,target_height,target_depth), load_size=limit_size)
features, labels = mri_loader.Load_Data()

# Dataset Information
dataset_size = len(labels['conversion'])
print("\n--- DATASET INFORMATION ---")
print("DATASET SIZE: " + str(dataset_size))

strategy = tf.distribute.MirroredStrategy()

metrics_dict = None
epoch = None

train_times = []

with strategy.scope():
  # Training iterations
  for i in range(iterations):
    # Model definition
    model = MudNet(features_shape_dict, output_class_dict, regularizer, dropout_rate, learning_rate)
    # Display model info
    if (i == 0):
      print("\n--- MODEL INFORMATION ---")
      print(model.summary())
      
    print("\n--- ITERATION " + str(i) + " ---")
    
    # Generate callbacks
    Record_Metrics = Metrics_Conversion_Risk()
    Plateau_Decay = LR_Plateau(factor=0.1, patience=2)
    callbacks_inital = [EarlyStopping(monitor='val_loss', patience=15), Plateau_Decay, Record_Metrics]
    
    #conversion_class_weights = compute_class_weight('balanced', np.unique(labels['conversion']), labels['conversion'])
    #risk_class_weights = compute_class_weight('balanced', np.unique(labels['risk']), labels['risk'])
    
    # Create split training/test dataset
    mri_train, mri_test, clinical_train, clinical_test, conversion_train, conversion_test, risk_train, risk_test = Train_Test_Split(features, labels, test_size)
    
    # One-Hot Encoding
    encoded_train_risk = One_Hot_Encode(risk_train, output_class_dict['risk'])
    encoded_test_risk = One_Hot_Encode(risk_test, output_class_dict['risk'])
    
    # Create tf.data train/test dataset
    train_dataset = tf.data.Dataset.from_tensor_slices(({'mri_features':mri_train, 'clinical_features':clinical_train},
    {'Conversion':conversion_train,'Risk':encoded_train_risk}))
    train_dataset = train_dataset.batch(batch_size)
    train_dataset = train_dataset.prefetch(prefetch_size)
    test_dataset = tf.data.Dataset.from_tensor_slices(({'mri_features':mri_test, 'clinical_features':clinical_test},
    {'Conversion':conversion_test,'Risk':encoded_test_risk}))
    test_dataset = test_dataset.batch(batch_size)
    test_dataset = test_dataset.prefetch(prefetch_size)
    
    # Timer
    start = time.time()
    # Training
    results = model.fit(train_dataset, epochs=epochs, validation_data=test_dataset, verbose=1, shuffle=True, use_multiprocessing=True, callbacks=callbacks_inital)
    #class_weight={'Conversion': {0: conversion_class_weights[0], 1:conversion_class_weights[1]}, 'Risk': {0:risk_class_weights[0], 1:risk_class_weights[1], 
    #  2:risk_class_weights[2]}})
    end = time.time()  
    
    train_time = (end-start)/60
    print("Total training time: " + str(train_time) + " min")
    train_times.append(train_time)
    
    metrics_dict = results.history
    epoch = results.epoch

print("\n --- FINAL TEST RESULTS ---")
print("Final avg. training time:", np.mean(np.asarray(train_times)))
print()
print("Conversion: " + str(metrics_dict['val_Conversion_binary_accuracy']) + "\tRisk: " + str(metrics_dict['val_Risk_categorical_accuracy']))
print()
print("Conversion Accuracy:", metrics_dict['val_Conversion_binary_accuracy'])
print("Risk Accuracy:", metrics_dict['val_Risk_categorical_accuracy'])
print()

# plot metrics
plot_metrics(metrics_dict, epoch)