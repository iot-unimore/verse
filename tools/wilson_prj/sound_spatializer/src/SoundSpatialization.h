/**
*
* \brief This is the header file of the example project 1 using 3D Tune-In Toolkit
* \date	April 2018
*
* \authors A. Rodríguez-Rivero, as part of the 3DI-DIANA Research Group (University of Malaga)
* \b Contact: A. Reyes-Lecuona as head of 3DI-DIANA Research Group (University of Malaga): areyes@uma.es
*
* \b Contributions: (additional authors/contributors can be added here)
*
* \b Project: 3DTI (3D-games for TUNing and lEarnINg about hearing aids) ||
* \b Website: http://3d-tune-in.eu/
*
* \b Copyright: University of Malaga - 2018
*
* \b Licence: GPLv3
*
* \b Acknowledgement: This project has received funding from the European Union's Horizon 2020 research and innovation programme under grant agreement No 644051
*
*/

#ifndef _H_SOUND_SPATIALISATION_H_
#define _H_SOUND_SPATIALISATION_H_


#include <cstdio>
#include <cstring>
#include <HRTF/HRTFFactory.h>
#include <HRTF/HRTFCereal.h>
#include <BRIR/BRIRFactory.h>
#include <BRIR/BRIRCereal.h>
#include <BinauralSpatializer/3DTI_BinauralSpatializer.h>

/* 3D-TuneIn core */
Binaural::CCore							myCore;												 // Core interface

/* Listener */
shared_ptr<Binaural::CListener>			listener;											 // Pointer to listener interface

/* Room */
shared_ptr<Binaural::CEnvironment>      environment;                                         // pointer to environment interface

/* Output */
Common::CEarPair<CMonoBuffer<float>>    outputBufferStereo;                                  // Stereo buffer containing processed audio

/* Sound Sources */
vector<shared_ptr<Binaural::CSingleSourceDSP>>     soundSources;                             // vector of sound sources to render
vector<Common::CTransform>                         soundSourcesPosition;                     // vector of sound sources position to render
vector<SNDFILE*>                                   soundSourcesFile;                         // vector of sound sources input file handlers
vector<SF_INFO>                                    soundSourcesFileInfo;                     // vector of sound sources input file audio info
std::vector<std::vector<std::vector<std::string>>> soundSourcesPath;                         // vector of CSV for source motion definition
std::vector<uint32_t>                              soundSourcesPathIdx;


#endif
