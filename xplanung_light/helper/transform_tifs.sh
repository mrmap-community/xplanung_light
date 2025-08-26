#!/bin/bash
# Define the target directory
#directory="/home/armin/GDI-RP/xplanung/testdaten/komserv/rieden/BPlan2/07137093_Rieden/raster2"
#directory="/home/armin/GDI-RP/xplanung/testdaten/komserv/mendig/BPlan2/07137069_Mendig/raster2"
# Script thinks that the tif has srs 31466!
# It will destroy the reference, if the image is not given in 31466
directory=$1
# Check if the target is not a directory
if [ ! -d "$directory" ]; then
  exit 1
fi
# Loop through files in the target directory
for file in "$directory"/*.plan.tif; do
  if [ -f "$file" ]; then
    echo "$file"
    gdal_translate -a_srs EPSG:31466 -co "TFW=YES" "$file" tmp_plan_geo.tif
    gdalwarp -t_srs EPSG:25832 tmp_plan_geo.tif tmp_plan_geo_utm32.tif
    gdal_translate  tmp_plan_geo_utm32.tif tmp_plan_geo_utm32_lzw.tif -co COMPRESS=LZW
    gdaladdo -r average tmp_plan_geo_utm32_lzw.tif
    
    cp tmp_plan_geo_utm32_lzw.tif "$file"
    
    rm tmp_plan_geo.tif
    rm tmp_plan_geo_utm32.tif
    rm tmp_plan_geo_utm32_lzw.tif
     
  fi
done

