diff --git a/3dti_Toolkit/BinauralSpatializer/HRTF.cpp b/3dti_Toolkit/BinauralSpatializer/HRTF.cpp
index aaa0440..ee287bb 100644
--- a/3dti_Toolkit/BinauralSpatializer/HRTF.cpp
+++ b/3dti_Toolkit/BinauralSpatializer/HRTF.cpp
@@ -1438,10 +1438,15 @@ namespace Binaural
 		//The common delay of each canal have been calculated and subtracted separately in order to correct the asymmetry of the measurement
 		if (minimumDelayRight != 0 || minimumDelayLeft != 0) 
 		{
+			int minDelay = (minimumDelayLeft < minimumDelayRight) ? minimumDelayLeft : minimumDelayRight;
+
 			for (auto it = t_HRTF_DataBase.begin(); it != t_HRTF_DataBase.end(); it++)
 			{
-				it->second.leftDelay = it->second.leftDelay - minimumDelayLeft;		//Left ear
-				it->second.rightDelay = it->second.rightDelay - minimumDelayRight;	//Right ear
+				// it->second.leftDelay = it->second.leftDelay - minimumDelayLeft;      //Left ear
+				// it->second.rightDelay = it->second.rightDelay - minimumDelayRight;	//Right ear
+
+				it->second.leftDelay = it->second.leftDelay - minDelay;		//Left ear
+				it->second.rightDelay = it->second.rightDelay - minDelay;	//Right ear
 			}
 		}
 
