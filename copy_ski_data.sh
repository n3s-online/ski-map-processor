#!/bin/bash

# Create target directories if they don't exist
mkdir -p "../ski-o-guessr/src/assets/ski-data"
mkdir -p "../ski-o-guessr/public/ski-images"

# 1. Copy index.json to the target directory
echo "Copying index.json..."
cp "files/index.json" "../ski-o-guessr/src/assets/ski-data/"

# 2. Copy metadata.json from each folder
echo "Copying metadata.json files..."
for folder in files/*/; do
  folder_name=$(basename "$folder")
  
  # Create target directory for metadata
  mkdir -p "../ski-o-guessr/src/assets/ski-data/$folder_name"
  
  # Copy metadata.json
  if [ -f "$folder/metadata.json" ]; then
    cp "$folder/metadata.json" "../ski-o-guessr/src/assets/ski-data/$folder_name/"
    echo "  Copied metadata.json from $folder_name"
  else
    echo "  Warning: No metadata.json found in $folder_name"
  fi
  
  # 3. Copy images to public directory
  mkdir -p "../ski-o-guessr/public/ski-images/$folder_name"
  
  # Find all PNG images in the folder and copy them
  image_count=0
  for image in "$folder"/*.png; do
    if [ -f "$image" ]; then
      image_filename=$(basename "$image")
      cp "$image" "../ski-o-guessr/public/ski-images/$folder_name/$image_filename"
      image_count=$((image_count + 1))
    fi
  done
  
  if [ $image_count -gt 0 ]; then
    echo "  Copied $image_count images from $folder_name"
  else
    echo "  Warning: No PNG images found in $folder_name"
  fi
done

echo "Done!" 