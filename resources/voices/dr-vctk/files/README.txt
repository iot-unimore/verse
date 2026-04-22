==============================================================
 Device Recorded VCTK (Small subset version)                        
 
 RELEASE November 2017  
                                                                
 National Institute of Informatics (NII)
 JAPAN
 Copyright (c) 2017  

 The Centre for Speech Technology Research (CSTR)
 University of Edinburgh
 UK 
 Copyright (c) 2017  

 Dr. Junichi Yamagishi
 jyamagis@nii.ac.jp
 jyamagis@inf.ed.ac.uk
===============================================================


---OVERVIEW---
This dataset is a new variant of the voice cloning toolkit (VCTK) dataset [1]: 
device-recorded VCTK (DR-VCTK), where high-quality speech signals recorded 
in a semi-anechoic chamber using professional audio devices have been played back 
and re-recorded in office environments using relatively inexpensive consumer 
devices.

Using the parallel database of the original VCTK and DR-VCTK, we can consider 
data-driven mapping between device-recorded and high-quality audio. 

This package has a small preprocessed version of DR-VCTK used for our recent 
experiments to be published soon. 

The entire DR-VCTK dataset has 243GB. If you are interested in acquiring this, 
please contact Junichi Yamagishi (jyamagis@nii.ac.jp). 


Reference:
[1] Christophe Veaux, Junichi Yamagishi, Kirsten MacDonald,
CSTR VCTK Corpus: English Multi-speaker Corpus for CSTR Voice Cloning Toolkit, 
University of Edinburgh. The Centre for Speech Technology Research (CSTR). 
http://dx.doi.org/10.7488/ds/1994.


---DESCRIPTIONS---
We used the original VCTK corpus as the clean speech-signal source for the 
device-recorded signals, as it was recorded at high-quality using professional 
audio devices. This dataset contains recordings of 109 English speakers with 
different accents. There are around 400 sentences available from each speaker.

Audio signals included in the CSTR VCTK corpus were played back from a loudspeaker 
and re-recorded using relatively inexpensive consumer devices in office 
environments. 

We used the eight different microphones below for the recording of the device-recorded 
speech signals: 

Channel 1         MacBookAir (ch.1)
Channel 2         MacBookAir (ch.2)
Channel 3         Apogee MiC
Channel 4         Blue Snowball
Channel 5         iPhone 5S (ch.1)
Channel 6         iPhone 5S (ch.2)
Channel 7         iPad (ch.1)
Channel 8         iPad (ch.2)

The setup for device-recording is shown in a picture included in this package. 

Bose 404600 SoundLink speaker III was used as a high-quality speaker, and was set 
2 meters from the microphones. Recording was done in a medium-sized office under 
two background-noise conditions (i.e. windows either opened or closed). 
We recorded device-recorded signals under 16 conditions (8 microphones x 
2 background noise conditions). All data was recorded at 48 kHz.

Among the 109 speakers, we selected 28 speakers (14 male and 14 female with 
British received pronunciation accent) for training and selected 2 speakers 
(1 male and 1 female) who had the same accent for testing. 

Twelve out of the 16 recording conditions were used for training and the 
remaining 4 recording conditions were used for testing. Half of the recording 
conditions in the training set (6 out of 12 sets) and half of those in the 
test sets (2 out of 4 sets) were selected from the windows-open background-noise 
condition. In other words, there was neither overlapped speakers nor recording 
conditions between training and test sets. However, each of the training and 
test sets included speech data under both windows-open and windows-closed 
background-noise conditions.

We used auto-correlation for removing the delay between clean and playback data. 
Silence segments longer than 200 ms were trimmed from the beginning and end of 
each sentence. We then down-sampled the dataset to 16 kHz for this package.


---STRUCTURE---
This dataset contains of four folders for train and test sets in clean and 
device-recorded conditions. 

The clean conditions are based on the original VCTK corpus. 

Channel 3 and 7 of DR-VCTK dataset in opened and closed window conditions were 
used as test set of the device-recorded conditions, and the other 12 device-recorded 
conditions were used as train set. 

Specifications of the recording conditions of each device-recorded sample 
in train and test sets are shown in train_ch_log.txt and test_ch_log.txt files 
respectively, located under the configurations folder.  

Objective measures of each device-recorded sample in train and test sets are 
also shown in train.txt and test.txt files respectively, located under objective-measures
folder.  

The measures have been computed using the implementation publicly available at 
https://www.crcpress.com/downloads/K14513/K14513_CD_Files.zip
Estimated SNR and SSNR are computed after removing the DC shift and normalizing 
the amplitude of the enhanced signal.


---COPYING---
You are free to use this database under Creative Commons Attribution License (CC-BY). 

Regarding Creative Commons License: Attribution 4.0 International (CC BY 4.0), 
please see https://creativecommons.org/licenses/by/4.0/

THIS DATABASE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND 
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
ARISING IN ANY WAY OUT OF THE USE OF THIS DATABASE, EVEN IF ADVISED OF THE 
POSSIBILITY OF SUCH DAMAGE.


---ACKNOWLEDGEMENTS---
This project was conducted during an internship of Mr. Seyyed Saeed Sarfjoo 
(saeed.sarfjoo@ozu.edu.tr) at NII, Japan under the guidance and supervision 
by Dr. Junichi Yamagishi and other NII members. His internship was finically 
supported by NII and this recording was partially supported by MEXT KAKENHI 
Grant Numbers (15H01686, 16H06302, 17H04687).


