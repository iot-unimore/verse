==============================================================================
resources: a collection of data and script needed to create a dataset
==============================================================================

voices: human voice recording, without any reverberation, mono audio file

rooms: binaural-room-impulse-response (BRIR) for reverberation computation.
       must be in spatially-oriented-format_for_acoustics (SOFA)

heads: head-related-transfer-functions (HRTF) of a specific head with binaural
       or multi-microphone placement. note: must be in 3d-TuneIn SOFA format,
       see https://3d-tune-in.eu/ and AES69-2022

paths: definition of a dynamic path in space for a single audio source,
       used to simulate the motion of a source during audio rendering.
       coordinates are referred to the head positioning (origin)

scenes: a combination of voices+paths, heads, rooms to define audio rendering
        for a specific use case (static positioning, dynamic positioning
        single/multiple voices etc.). Paths are used in a scene to define
        the geometry of the scene itself.

ds_recipes: info and scripts to create a complete audio rendering dataset
        based on a given list of sceners and/or voice/heads/rooms.

