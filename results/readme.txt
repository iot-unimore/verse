comparing "plain" HRTF rendering with real recording:

HRTFS:
unimore,head_004
-rw-rw-r-- 1 gfilippi gfilippi 6899657 ago 18 13:00 wilsonClean_20250817-001_array_six_front.sofa
-rw-rw-r-- 1 gfilippi gfilippi 6905446 ago 18 13:00 wilsonClean_20250817-001_array_six_middle.sofa
-rw-rw-r-- 1 gfilippi gfilippi 6900144 ago 18 13:00 wilsonClean_20250817-001_array_six_rear.sofa
-rw-rw-r-- 1 gfilippi gfilippi 6923968 ago 18 13:00 wilsonClean_20250817-001_binaural.sofa


RECORDINGS:
azimuth: [0:10:360] # start,stop, step
elevation: [-45,-30,-15,0,15,30,45]
auralys_measures/wilsonAudio_20250818_001

COMPARE:
(make sure to modify the script for recorded audio file locations)
python ./computeMapWPPAS.py -v  -i ../datasets/static_singlevoice/train/000004_static_singlevoice_0_0_1/static_singlevoice.mkv -c 16
