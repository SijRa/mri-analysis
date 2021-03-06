from os import listdir, rename
from shutil import rmtree

# location for extracted brain and masks
directory = "AD_NL_Brains/"
mask_directory = "AD_NL_Masks/"

# Rename files
for folder in listdir(directory):
  mri_extracted = directory + folder + "/" + "brain.nii"
  mri_mask = directory + folder + "/" + "brain_mask.nii"
  id = folder.split('.')[0]
  new_extracted = directory + id + "+brain.nii"
  new_mask = mask_directory + id + ".nii"
  rename(mri_extracted, new_extracted)
  rename(mri_mask, new_mask)
  print("Renamed Filed: " + new_extracted)
  path = directory + folder
  rmtree(path)
  print("Deleted folder:", folder)