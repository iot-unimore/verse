#if defined( __linux__ ) || defined( linux )
    # include <bits/stdc++.h>
#endif

#include <signal.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <iostream>
#include <getopt.h>
#include <cstdlib>
#include <math.h>
#include <inttypes.h>

#include <sndfile.h>

#include "SoundSpatialization.h"
#include "progressbar.h"
#include "logger.h"
#include "YAMLReader.h"
#include "YAMLConfigDefault.h"
#include "CSVReader.h"

/*******************************************************************************
 * Macros & Defines
 *******************************************************************************/

#define SW_VER_MJR                      ( 1 )
#define SW_VER_MIN                      ( 0 )
#define SW_VER_REV                      ( 2 )

#define MAX_SAMPLERATE             ( 192000 )

#define HRTF_RESAMPLING_STEPS_DEG      ( 15 )

#define MAX_BUFFER_LEN              ( 16384 )
#define BUFFER_LEN                   ( 4096 )

/* input files should be audio MONO sources */
#define MAX_CHANNELS ( 1 )

/* max number of sources (wav) files we handle */
#define MAX_SOURCES ( 16 )

/* for input coordinates decoding */
#define COORD_TYPE_CARTESIAN ( 0 )
#define COORD_TYPE_SPHERICAL ( 1 )


/*******************************************************************************
 * Global Variables
 *******************************************************************************/

/*  This will be the length of the buffer used to hold audio frames */
uint16_t                 iBufferSize = BUFFER_LEN;

bool                     bEnableReverb = false;

volatile uint8_t         verbosity = LOG_ZERO;
volatile bool            bCtrlExit = false;


/*
 * CLI
 */

static const char* const short_opts = "i:o:v:r:s:p:b:c:h";

static const option      long_opts[] = {
    { "input",         required_argument, nullptr, 'i' },
    { "output",        required_argument, nullptr, 'o' },
    { "coords_source", required_argument, nullptr, 'c' },
    { "verbosity",     required_argument, nullptr, 'v' },
    { "hrtf_sofa",     required_argument, nullptr, 's' },
    { "brir_sofa",     required_argument, nullptr, 'r' },
    { "params",        required_argument, nullptr, 'p' },
    { "buflen",        required_argument, nullptr, 'b' },
    { "help",          no_argument,       nullptr, 'h' },
    { nullptr,         0,                 nullptr, 0   }
};


/*******************************************************************************
 * Function Prototypes
 *******************************************************************************/

/*******************************************************************************
 * Function Name: print_help( )
 *******************************************************************************
 * Summary: print CLI help
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
void print_help( )
{
    LOG_PRINTF( "SoundSpatializer v.%d.%d.%d\n\n", SW_VER_MJR, SW_VER_MIN, SW_VER_REV );
    std::cout << "Usage: sspat [options]\n"
              << "Options:\n"
              << "  -i, --input <file>            Input .WAV file\n"
              << "  -o, --output <file>           Output .WAV file\n"
              << "  -c, --coord_source <a,e,d>    Source coordinates (spherical)\n"
              << "  -s, --hrtf_sofa <file>        Specify Head HRTF SOFA file\n"
              << "  -r, --brir_sofa <file>        Specify Room Reverb SOFA file\n"
              << "  -v, --verbosity <level>       Set verbosity level\n"
              << "  -b, --buflen <number>         Set audio buffer size (max: " << MAX_BUFFER_LEN << ")\n"
              << "  -p, --params <file>           Params file (YAML)\n"
              << "  -h, --help                    Show this help message and quit\n";
}


/*******************************************************************************
 * Function Name: print_summary( )
 *******************************************************************************
 * Summary: print CLI summary
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
void print_summary( YAML::Node yaml_config, std::string output_file )
{
    int8_t sources_count = ( yaml_config )[ "setup" ][ "sources_count" ].as<int>( );

    LOG_MSG( LOG_LOW, verbosity, "==================================================\n" );
    LOG_MSG( LOG_LOW, verbosity, " SUMMARY:\n" );
    LOG_MSG( LOG_LOW, verbosity, "==================================================\n" );

    LOG_MSG( LOG_LOW, verbosity, "Sources Count: %2d, \n", sources_count );

    for ( int8_t idx = 0; idx < sources_count; idx++ )
    {
        LOG_MSG( LOG_LOW, verbosity, "Source #%2d\n  Input file: %s\n", idx, yaml_config[ "setup" ][ "sources" ][ idx ][ "file_wav" ].as<std::string>( ).c_str( ) );
        LOG_MSG( LOG_LOW, verbosity, "  Coord: %s\n",                   yaml_config[ "setup" ][ "sources" ][ idx ][ "coord" ].as<std::string>( ).c_str( ) );
        LOG_MSG( LOG_LOW, verbosity, "  Path: %s\n",                    yaml_config[ "setup" ][ "sources" ][ idx ][ "path_csv" ].as<std::string>( ).c_str( ) );
    }

    LOG_MSG( LOG_LOW, verbosity, "Head, hrtf file: %s\n",        yaml_config[ "setup" ][ "head" ][ "hrtf_sofa" ].as<std::string>( ).c_str( ) );
    LOG_MSG( LOG_LOW, verbosity, "Room, brir file: %s\n",        yaml_config[ "setup" ][ "room" ][ "brir_sofa" ].as<std::string>( ).c_str( ) );
    LOG_MSG( LOG_LOW, verbosity, "Output file: %s\n",            output_file.c_str( ) );
    LOG_MSG( LOG_LOW, verbosity, "Reverb is %s\n",               bEnableReverb ? "enabled" : "disabled" );
    LOG_MSG( LOG_LOW, verbosity, "Verbosity level set to: %d\n", verbosity );
    LOG_MSG( LOG_LOW, verbosity, "==================================================\n" );
}


/*******************************************************************************
 * Function Name: ctrlHandler( )
 *******************************************************************************
 * Summary: install handler for CTRL-C signal catch
 *
 * Parameters:
 *  event: (unused)
 *
 * Return:
 *  None
 *
 *******************************************************************************/
void ctrlHandler( int s )
{
    LOG_MSG( LOG_DEBUG,  verbosity, "Caught signal %d\n", s );
    LOG_MSG( LOG_ALWAYS, verbosity, "Got CTRL-C ... exiting.\n" );

    bCtrlExit = true;
}


/*******************************************************************************
 * Function Name:
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
inline float fmod_positive( float x, float y )
{
    return x < 0 ? ( fmod( x, y ) + y ) : fmod( x, y );
}


/*******************************************************************************
 * Function Name:
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t csvSearchNextIndex( std::vector<std::vector<std::string> >& csvText, uint32_t* idx, float key )
{
    uint32_t tmpIdx = 0;

    if ( NULL != idx )
    {
        tmpIdx = *idx;

        float tmpKey = key;
        float tmpVal = std::stof( csvText[ tmpIdx ][ 0 ] );

        if ( tmpIdx >= csvText.size( ) )
        {
            return -1;
        }

        while ( ( tmpVal < tmpKey ) && ( tmpVal < 100.0f ) && ( ( tmpIdx + 1 ) < csvText.size( ) ) )
        {
            tmpIdx++;

            tmpVal = std::stof( csvText[ tmpIdx ][ 0 ] );
        }

        if ( NULL != idx )
        {
            *idx = tmpIdx;
        }

        return 0;
    }
    else
    {
        return -1;
    }
}


/*******************************************************************************
 * Function Name:
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
void yamlProcessNode( const YAML::Node& node )
{
    if ( node.IsMap( ) )
    {
        // Handle map (key-value pairs)
        for ( const auto& item : node )
        {
            ////std::cout << "Map - Key: " << item.first.as<std::string>( ) << std::endl;
            // Recursively process the value (it could be a map, sequence, or scalar)
            if ( item.second.IsMap( ) || item.second.IsSequence( ) )
            {
                yamlProcessNode( item.second );
            }
            else
            {
                // For scalars, just print the value
                ////std::cout << "  Value: " << item.second.as<std::string>( ) << std::endl;
            }
        }
    }
    else if ( node.IsSequence( ) )
    {
        // Handle sequence (array)
        ////std::cout << "Sequence:" << std::endl;
        for ( const auto& item : node )
        {
            // Recursively process sequence items
            yamlProcessNode( item );
        }
    }
    else
    {
        // Handle scalar value
        ////std::cout << "Scalar Value: " << node.as<std::string>( ) << std::endl;
    }
}


/*******************************************************************************
 * Function Name:
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t yamlOpenFile( std::string yaml_file, YAML::Node* yaml_config )
{
    int8_t err = 0;

    if ( NULL == yaml_config )
    {
        return -1;
    }

    if ( yaml::YAMLReader::readYAML( yaml_file, *yaml_config ) )
    {
        yaml::YAMLReader::traverseYAMLNode( *yaml_config, yamlProcessNode );  // Process the root and its children
    }
    else
    {
        std::cerr << "Failed to read the YAML file!" << std::endl;
    }

    return err;
}


/*******************************************************************************
 * Function Name:
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t setConfigParams( YAML::Node* yaml_config )
{
    int8_t      err = 0;

    int8_t      sources_count = ( *yaml_config )[ "setup" ][ "sources_count" ].as<int>( );

    if ( sources_count > MAX_SOURCES )
    {
        LOG_ERR( LOG_ALWAYS, verbosity, "Error: too many audio sources in config file." )
        return -1;
    }

    for ( int8_t idx = 0; idx < sources_count; idx++ )
    {
        std::cout << "\n" << std::to_string( idx ) << std::endl;

        std::cout << ( *yaml_config )[ "setup" ][ "sources" ][ idx ][ "file_wav" ] << std::endl;
        std::cout << ( *yaml_config )[ "setup" ][ "sources" ][ idx ][ "coord" ] << std::endl;
        std::cout << ( *yaml_config )[ "setup" ][ "sources" ][ idx ][ "path_csv" ] << std::endl;
    }

    std::cout << ( *yaml_config )[ "setup" ][ "head" ][ "hrtf_sofa" ] << std::endl;

    std::cout << ( *yaml_config )[ "setup" ][ "room" ][ "brir_sofa" ] << std::endl;

    std::string hrtf_sofa_file = ( *yaml_config )[ "setup" ][ "head" ][ "hrtf_sofa" ].as<std::string>( );
    if ( 0 != hrtf_sofa_file.compare( "none" ) )
    {
        bEnableReverb = true;
    }

    return 0;
}


/*******************************************************************************
 * Function Name: openInputFile()
 *******************************************************************************
 * Summary: print CLI help
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t openInputFile( std::string input_file, SNDFILE** infile, SF_INFO* infile_sfinfo, uint8_t max_channels )
{
    const char* infilename = input_file.c_str( );

    /* Open the input file. */
    if ( !( *infile = sf_open( infilename, SFM_READ, infile_sfinfo ) ) )   /* Open failed so print an error message. */
    {
        LOG_MSG( LOG_ALWAYS, verbosity, "Not able to open input file {%s}.\n", infilename );
        /* Print the error message from libsndfile. */
        puts( sf_strerror( NULL ) );
        return -1;
    }

    if ( max_channels > 0 )
    {
        if ( infile_sfinfo->channels > max_channels )
        {
            LOG_MSG( LOG_ALWAYS, verbosity, "Not able to process more than {%d} channels\n", MAX_CHANNELS );

            sf_close( ( *infile ) );

            return -1;
        }
    }

    return 0;
}


int8_t closeInputFiles( vector<SNDFILE*>& soundSourcesFile )
{
    for ( int i = 0; i < soundSourcesFile.size( ); i++ )
    {
        if ( NULL != soundSourcesFile[ i ] )
        {
            sf_close( soundSourcesFile[ i ] );
        }
    }

    return 0;
}


int8_t openInputFiles( YAML::Node                                            yaml_config,
                       vector<SNDFILE*>&                                     soundSourcesFile,
                       vector<SF_INFO>&                                      soundSourcesFileInfo,
                       std::vector<std::vector<std::vector<std::string> > >& soundSourcesPath,
                       vector<uint32_t>&                                     soundSourcesPathIdx,
                       uint16_t*                                             sources_cnt,
                       uint8_t                                               max_channels )
{
    int8_t   err = 0;

    SNDFILE* infile;
    SF_INFO  infile_sfinfo;

    int8_t   sources_count = yaml_config[ "setup" ][ "sources_count" ].as<int>( );

    if ( MAX_SOURCES < sources_count )
    {
        return -1;
    }

    LOG_MSG( LOG_LOW, verbosity, "Opening Input Audio files (count=%d)\n", sources_count );

    if ( NULL != sources_cnt )
    {
        *sources_cnt = sources_count;
    }

    for ( int8_t idx = 0; idx < sources_count; idx++ )
    {
        err = 0;

        LOG_MSG( LOG_MEDIUM, verbosity, "Source #%d\n", idx );

        /*
         * audio files
         */
        std::string infilename = yaml_config[ "setup" ][ "sources" ][ idx ][ "file_wav" ].as<std::string>( );

        LOG_MSG( LOG_MEDIUM, verbosity, "  Opening file: %s\n", infilename.c_str( ) );

        if ( !( infile = sf_open( infilename.c_str( ), SFM_READ, &infile_sfinfo ) ) )
        {
            LOG_ERR( LOG_ALWAYS, verbosity, "Not able to open input file {%s}.\n", infilename.c_str( ) );
            /* Print the error message from libsndfile. */
            puts( sf_strerror( NULL ) );
            err = -1;
        }

        if ( max_channels > 0 )
        {
            if ( infile_sfinfo.channels > max_channels )
            {
                LOG_ERR( LOG_ALWAYS, verbosity, "Not able to process more than {%d} channels\n", MAX_CHANNELS );

                sf_close( infile  );

                err = -1;
            }
        }


        /*
         * CSV files
         */
        infilename = yaml_config[ "setup" ][ "sources" ][ idx ][ "path_csv" ].as<std::string>( );

        if ( ( !( infilename.empty( ) ) ) && ( 0 != infilename.compare( "none" )  ) )
        {
            std::vector<std::vector<std::string> > data;

            LOG_MSG( LOG_MEDIUM, verbosity, "  Opening file: %s\n", infilename.c_str( ) );

            if ( csv::CSVReader::readCSV( infilename, data ) )
            {
                soundSourcesPath.push_back( data );
                soundSourcesPathIdx.push_back( 0 );

                LOG_MSG( LOG_MEDIUM, verbosity, "CSV file %s read OK\n", infilename.c_str( ) );
            }
            else
            {
                err = -1;
                LOG_ERR( LOG_ALWAYS, verbosity, "Failed to read the CSV: %s\n", infilename.c_str( ) );
            }
        }
        else
        {
            // std::vector<std::vector<std::string>> data;
            // data.push_back({"none"});

            soundSourcesPath.push_back( { { "none" } } );
            soundSourcesPathIdx.push_back( 0 );
        }


        if ( 0 == err )
        {
            /* push back to vectors */
            soundSourcesFile.push_back( infile );
            soundSourcesFileInfo.push_back( infile_sfinfo );
        }
        else
        {
            break;
        }
    }


    return err;
}


int8_t findSourceMaxLen( YAML::Node yaml_config, vector<SF_INFO>& soundSourcesFileInfo, uint64_t* max_len )
{
    int8_t   err = 0;

    int8_t   sources_count = yaml_config[ "setup" ][ "sources_count" ].as<int>( );

    uint64_t len = 0;

    if ( MAX_SOURCES < sources_count )
    {
        return -1;
    }

    LOG_MSG( LOG_LOW, verbosity, "Opening Input Audio files (count=%d)\n", sources_count );

    for ( int8_t idx = 0; idx < sources_count; idx++ )
    {
        err = 0;
        if ( soundSourcesFileInfo[ idx ].frames > len )
        {
            len = soundSourcesFileInfo[ idx ].frames;
        }
    }

    if ( 0 == err )
    {
        if ( NULL != max_len )
        {
            *max_len = len;
        }
    }

    return err;
}


/*******************************************************************************
 * Function Name: openOutputFile()
 *******************************************************************************
 * Summary: print CLI help
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t openOutputFile( std::string output_file, SNDFILE** outfile, SF_INFO* outfile_sfinfo )
{
    const char* outfilename = output_file.c_str( );

    if ( !( *outfile = sf_open( outfilename, SFM_WRITE, outfile_sfinfo ) ) )
    {
        LOG_MSG( LOG_ALWAYS, verbosity, "Not able to open output file {%s}.\n", outfilename );
        puts( sf_strerror( NULL ) );
        return -1;
    }

    return 0;
}


/*******************************************************************************
 * Function Name: coordDecode( )
 *******************************************************************************
 * Summary: print CLI help
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t coordDecode( std::string input_str, uint8_t coordType, float* coord, uint8_t coord_cnt, bool positive_range )
{
    int8_t err = -1;

    if ( coord_cnt < 3 )
    {
        return err;
    }

    if ( coordType == COORD_TYPE_SPHERICAL )
    {
        if ( NULL != coord  )
        {
            float       tmp_coord[ 3 ] = { 0.0f };

            const char* temp = input_str.c_str( );
            char        string[ sizeof input_str.c_str( ) ] = "";

            float       value = 0.0f;
            int         count = 0;
            int         parsed = 0;

            err = 0;
            while ( ( err == 0 ) && ( !( bCtrlExit ) ) && ( 1 == sscanf( temp, "%11[^,],%n", string, &count ) ) )
            {
                temp += count;
                value = atof( string );

                switch ( parsed )
                {
                    case 0: /* AZIMUTH */

                        // if ( ( value >= 0 ) && ( value <= 359 ) )
                        // {
                        //     tmp_coord[ parsed ] = value;
                        // }
                        // else
                        // {
                        //     LOG_MSG( LOG_MEDIUM, verbosity, "coordDecode, invalid azimuth value\n" );
                        //     err = -1;
                        // }

                        // negative azimuth is positive on a 360 degree angle
                        if ( positive_range )
                        {
                            tmp_coord[ parsed ] = fmod_positive( value, 360.0 );
                        }
                        else
                        {
                            tmp_coord[ parsed ] = fmod( value, 360.0 );
                        }

                        break;

                    case 1: /* ELEVATION */

                        // if ( ( value >= -90 ) && ( value <= 90 ) )
                        // {
                        //     tmp_coord[ parsed ] = value;
                        // }
                        // else
                        // {
                        //     LOG_MSG( LOG_MEDIUM, verbosity, "coordDecode, invalid elevation value\n" );
                        //     err = -1;
                        // }

                        // saturate max min
                        value = ( value > 90.0 ) ?  90.0 : value;
                        value = ( value < -90.0 ) ? -90.0 : value;
                        tmp_coord[ parsed ] = value;

                        break;

                    case 2: /* DISTANCE */

                        if ( value >= 0 )
                        {
                            tmp_coord[ parsed ] = value;
                        }
                        else
                        {
                            LOG_MSG( LOG_MEDIUM, verbosity, "coordDecode, invalid distance value\n" );
                            err = -1;
                        }
                        break;

                    default:
                        err = -1;
                        break;
                }

                parsed++;
                if ( parsed >= 3 )
                {
                    break;
                }
            }

            if ( ( err == 0 ) && ( parsed == 3 ) )
            {
                coord[ 0 ] = tmp_coord[ 0 ];
                coord[ 1 ] = tmp_coord[ 1 ];
                coord[ 2 ] = tmp_coord[ 2 ];
            }
        }
    }
    return err;
}


/*******************************************************************************
 * Function Name: coordValidate( )
 *******************************************************************************
 * Summary: print CLI help
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t coordValidate(  float* coord, uint8_t coordType, uint8_t coord_cnt, bool positive_range )
{
    int8_t err = -1;
    float  tmp_coord[ 3 ] = { 0.0f };

    if ( coord_cnt < 3 )
    {
        return err;
    }

    if ( coordType == COORD_TYPE_SPHERICAL )
    {
        if ( NULL != coord  )
        {
            float value = 0.0f;

            /* AZIMUTH */
            if ( positive_range )
            {
                // negative azimuth is positive on a 360 degree angle
                tmp_coord[ 0 ] = fmod_positive( coord[ 0 ], 360.0 );
            }
            else
            {
                tmp_coord[ 0 ] = fmod( coord[ 0 ], 360.0 );
            }

            /* ELEVATION */
            // saturate max min
            value = coord[ 1 ];
            value = ( value > 90.0 ) ?  90.0 : value;
            value = ( value < -90.0 ) ? -90.0 : value;
            tmp_coord[ 1 ] = value;

            /* DISTANCE */
            value = coord[ 2 ];
            tmp_coord[ 2 ] = ( value < 0 ) ? ( 0.0f ) : value;

            err = 0;
        }

        // ... redundant ...
        if ( err == 0 )
        {
            coord[ 0 ] = tmp_coord[ 0 ];
            coord[ 1 ] = tmp_coord[ 1 ];
            coord[ 2 ] = tmp_coord[ 2 ];
        }
    }
    return err;
}


int8_t coordSumAndValidate(  float* coord1, float* coord2, uint8_t coordType, uint8_t coord_cnt )
{
    int8_t err = -1;
    float  tmp_coord[ 3 ] = { 0.0f };

    if ( coord_cnt < 3 )
    {
        return err;
    }

    if ( coordType == COORD_TYPE_SPHERICAL )
    {
        if ( ( NULL != coord1  ) && ( NULL != coord2 ) )
        {
            float value = 0.0f;
            float tmp_coord1[ 3 ] = { 0.0f };
            float tmp_coord2[ 3 ] = { 0.0f };

            // copy
            for ( int i = 0; i < 3; i++ )
            {
                tmp_coord1[ i ] = coord1[ i ];
                tmp_coord2[ i ] = coord2[ i ];
            }

            coordValidate( tmp_coord1, COORD_TYPE_SPHERICAL, sizeof( tmp_coord1 ) / sizeof( float ), true );
            coordValidate( tmp_coord2, COORD_TYPE_SPHERICAL, sizeof( tmp_coord1 ) / sizeof( float ), true );

            /* AZIMUTH */
            // negative azimuth is positive on a 360 degree angle
            tmp_coord[ 0 ] = fmod_positive( tmp_coord1[ 0 ] + tmp_coord2[ 0 ], 360.0 );

            /* ELEVATION */
            // saturate max min
            tmp_coord[ 1 ] = tmp_coord1[ 1 ] + tmp_coord2[ 1 ];

            /* DISTANCE */
            tmp_coord[ 2 ] = tmp_coord1[ 2 ] + tmp_coord2[ 2 ];

            coordValidate( tmp_coord, COORD_TYPE_SPHERICAL, sizeof( tmp_coord1 ) / sizeof( float ), true );

            err = 0;
        }

        // ... redundant ...
        if ( err == 0 )
        {
            coord1[ 0 ] = tmp_coord[ 0 ];
            coord1[ 1 ] = tmp_coord[ 1 ];
            coord1[ 2 ] = tmp_coord[ 2 ];
        }
    }
    return err;
}


/*******************************************************************************
 * Function Name: coordSphericalToCartesian( )
 *******************************************************************************
 * Summary: convert spherical to cartesian coordinates as per AES69-2022 spec
 *
 * Parameters:
 *  None
 *
 * Return:
 *  zero on success, negative on failure
 *
 *******************************************************************************/
int8_t coordSphericalToCartesian( float* in, uint8_t in_cnt, float* out, uint8_t out_cnt )
{
    int8_t err = -1;

    if ( ( NULL == in ) || ( NULL == out ) )
    {
        return err;
    }

    if ( ( in_cnt < 3 ) || ( out_cnt < 3 ) )
    {
        return err;
    }

    // cartesian: x = r * cos(pi/180*elevation) * cos(pi/180*azimuth)
    out[ 0 ] = in[ 2 ] * cos( M_PI / 180.0 * in[ 1 ] ) * cos( M_PI / 180.0 * in[ 0 ] );

    // cartesian: y = r * cos(pi.180*elevation) * sin(pi/180*azimuth)
    out[ 1 ] = in[ 2 ] * cos( M_PI / 180.0 * in[ 1 ] ) * sin( M_PI / 180.0 * in[ 0 ] );

    // cartesian: z = r * sin(pi/180* elevation)
    out[ 2 ] = in[ 2 ] * sin( M_PI / 180.0 * in[ 1 ] );

    return 0;
}


/*******************************************************************************
 * Function Name:
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  None
 *
 * Return:
 *  None
 *
 *******************************************************************************/
int8_t csvCoordInterpPosition( Common::CTransform&                     posCurrent, // current position
                               Common::CTransform&                     posNext,    // interpolated position
                               std::vector<std::vector<std::string> >& csvText,    // CSV path file
                               uint32_t                                currIdx,    // CSV current idx
                               uint32_t                                nextIdx,    // CSV next idx
                               uint64_t                                frames,
                               uint64_t                                frames_total )
{
    int8_t      err = -1;

    float       positionA[ 3 ] = { 0.0f };
    float       framesA = stof( csvText[ currIdx ][ 0 ] );
    std::string coordA = csvText[ currIdx ][ 2 ] + "," + csvText[ currIdx ][ 3 ] + "," + csvText[ currIdx ][ 4 ];

    float       positionB[ 3 ] = { 0.0f };
    float       framesB = stof( csvText[ nextIdx ][ 0 ] );
    std::string coordB = csvText[ nextIdx ][ 2 ] + "," + csvText[ nextIdx ][ 3 ] + "," + csvText[ nextIdx ][ 4 ];

    coordDecode( coordA.c_str( ), COORD_TYPE_SPHERICAL, positionA, sizeof( positionA ) / sizeof( float ), false );
    coordDecode( coordB.c_str( ), COORD_TYPE_SPHERICAL, positionB, sizeof( positionB ) / sizeof( float ), false );

    if ( framesB != framesA )
    {
        float alfa = ( (float) ( frames * 100.0f / frames_total )  - framesA ) / ( framesB - framesA );

        for ( int8_t i; i < 3; i++ )
        {
            positionA[ i ] = alfa * ( positionB[ i ] - positionA[ i ] ) + positionA[ i ];
        }

        coordValidate( positionA, COORD_TYPE_SPHERICAL, sizeof( positionA ) / sizeof( float ), true );

        coordSphericalToCartesian( positionA, sizeof( positionA ) / sizeof( float ), positionB, sizeof( positionB ) / sizeof( float ) );

        posNext.SetPosition( Common::CVector3( positionB[ 0 ], positionB[ 1 ], positionB[ 2 ] ) );

        err = 0;
    }
    else
    {
        // keep the same position
        err = -1;
    }

    return err;
}


/*******************************************************************************
 * Function Name: TuneInUserConfig( )
 *******************************************************************************
 * Summary: setup 3DTune-In library, set sources, listener and environment
 *
 * Parameters:
 *  None
 *
 * Return:
 *  zero on success, negative on failure
 *
 *******************************************************************************/
int8_t TuneInUserConfig(
    YAML::Node yaml_config,
    float      source_coord[ 3 ],
    uint16_t   bufferSize )
{
    float                     path_coord[ 3 ] = { 0.0f };
    float                     tmp_coord[ 3 ] = { 0.0f };


    /*
     * 3DTuneIn Core setup
     */
    ERRORHANDLER3DTI.SetVerbosityMode( VERBOSITYMODE_ERRORSANDWARNINGS );

    ERRORHANDLER3DTI.SetErrorLogStream( &std::cout, true );

    // Audio State struct declaration, set buffer size and samplerate
    Common::TAudioStateStruct audioState;

    audioState.bufferSize = bufferSize;
    audioState.sampleRate = soundSourcesFileInfo[ 0 ].samplerate; // sampleRate;

    // Applying configuration to core
    myCore.SetAudioState( audioState );

    // Setting 15-degree resampling step for HRTF
    myCore.SetHRTFResamplingStep( HRTF_RESAMPLING_STEPS_DEG );

    /*
     * Audio Listener setup posiiton and properties
     *
     */

    listener = myCore.CreateListener( );
    Common::CTransform        listenerPosition = Common::CTransform( );

    // Setting listener in (0,0,0)
    listenerPosition.SetPosition( Common::CVector3( 0, 0, 0 ) );
    listener->SetListenerTransform( listenerPosition );

    // Disabling custom head radius
    listener->DisableCustomizedITD( );

    /* HRTF can be loaded in either SOFA
     * (more info in https://sofacoustics.org/) or 3dti-hrtf format.
     * These HRTF files are provided with 3DTI Audio Toolkit.
     * They can be found in 3dti_AudioToolkit/resources/HRTF
     */
    bool                      specifiedDelays;

    // Comment this line and uncomment next lines to load the default HRTF in 3dti-hrtf format instead of in SOFA format
    // HRTF::CreateFrom3dti("hrtf.3dti-hrtf", listener);

    std::string               hrtf_sofa_file = yaml_config[ "setup" ][ "head" ][ "hrtf_sofa" ].as<std::string>( );
    if ( ( 0 < hrtf_sofa_file.length( ) ) && ( 0 != hrtf_sofa_file.compare( "none" ) ) )
    {
        HRTF::CreateFromSofa( hrtf_sofa_file.c_str( ), listener, specifiedDelays );
    }
    else
    {
        /* return error if we have no hrtf file */
        return -1;
    }


    /*
     * Audio Environment setup (Room)
     *
     */

    // Creating environment to have reverberated sound
    environment = myCore.CreateEnvironment( );

    // Setting number of ambisonic channels to use in reverberation processing
    environment->SetReverberationOrder( TReverberationOrder::BIDIMENSIONAL );

    // Loading SOFAcoustics BRIR file and applying it to the environment
    std::string               brir_sofa_file = yaml_config[ "setup" ][ "room" ][ "brir_sofa" ].as<std::string>( );
    if ( ( 0 < brir_sofa_file.length( ) ) && ( 0 != brir_sofa_file.compare( "none" ) ) )
    {
        BRIR::CreateFromSofa( brir_sofa_file.c_str( ), environment );
    }
    else
    {
        bEnableReverb = false;
    }

    /*
     * Loop on Audio Sources and setup DSP and positioning
     */
    int8_t                    sources_count = yaml_config[ "setup" ][ "sources_count" ].as<int>( );

    for ( int8_t idx = 0; idx < sources_count; idx++ )
    {
        // decode position, from str to numeric
        // if ( 0 != coordDecode( yaml_config[ "setup" ][ "sources" ][ idx ][ "coord" ].as<std::string>( ), COORD_TYPE_SPHERICAL, source_coord, sizeof( source_coord ) / sizeof( float ) , true) )
        if ( 0 != coordDecode( yaml_config[ "setup" ][ "sources" ][ idx ][ "coord" ].as<std::string>( ), COORD_TYPE_SPHERICAL, source_coord, 3, true ) )
        {
            std::cerr << "Error: invalid source coordinates (type is spherical).\n\n";
            return 1;
        }

        shared_ptr<Binaural::CSingleSourceDSP> tmpSource = myCore.CreateSingleSourceDSP( ); // Creating audio source

        // decode position, from spherical to cartesian
        float                                  tmp_coord[ 3 ] = { 0.0f };
        coordSphericalToCartesian( source_coord, sizeof( tmp_coord ) / sizeof( float ), tmp_coord, sizeof( tmp_coord ) / sizeof( float ) );

        Common::CTransform                     tmpSourcePosition = Common::CTransform( );
        tmpSourcePosition.SetPosition( Common::CVector3( tmp_coord[ 0 ], tmp_coord[ 1 ], tmp_coord[ 2 ] ) );

        if ( 0 != yaml_config[ "setup" ][ "sources" ][ idx ][ "path_csv" ].as<std::string>( ).compare( "none" ) )
        {
            std::string tmpStringCSV = soundSourcesPath[ idx ][ 0 ][ 2 ] + "," + soundSourcesPath[ idx ][ 0 ][ 3 ] + "," + soundSourcesPath[ idx ][ 0 ][ 4 ];

            if ( 0 == coordDecode( tmpStringCSV.c_str( ), COORD_TYPE_SPHERICAL, path_coord, sizeof( path_coord ) / sizeof( float ), true ) )
            {
                // coordSumAndValidate( source_coord, path_coord, COORD_TYPE_SPHERICAL, 3 );
                coordSphericalToCartesian( path_coord, sizeof( tmp_coord ) / sizeof( float ), tmp_coord, sizeof( tmp_coord ) / sizeof( float ) );
                tmpSourcePosition.SetPosition( Common::CVector3( tmp_coord[ 0 ], tmp_coord[ 1 ], tmp_coord[ 2 ] ) );
            }
        }

        // source config
        tmpSource->SetSourceTransform( tmpSourcePosition );
        tmpSource->SetSpatializationMode( Binaural::TSpatializationMode::HighQuality );  // HighPerformance vs HighQuality // Choosing high quality mode for anechoic processing
        tmpSource->DisableNearFieldEffect( );                                            // Audio source will not be close to listener, so we don't need near field effect
        tmpSource->EnableAnechoicProcess( );                                             // Setting anechoic and reverb processing for this source
        tmpSource->EnableDistanceAttenuationAnechoic( );
        tmpSource->EnablePropagationDelay( );                                            // Activate delay simulation due to the distance of the source

        /* push back into Sources vector */
        soundSources.push_back( tmpSource );

        /* dynamic source position */
        soundSourcesPosition.push_back( tmpSourcePosition );
    }

    return 0;
}


/*******************************************************************************
 * Function Name: TuneInAudioProcess( )
 *******************************************************************************
 * Summary:
 *
 * Parameters:
 *  event: (unused)
 *
 * Return:
 *  zero on success, negative on failure
 *
 *******************************************************************************/
int8_t TuneInAudioProcess(
    Common::CEarPair<CMonoBuffer<float> >&           bufferOutput,
    float                                            data[][ MAX_BUFFER_LEN ],
    int                                              count,
    vector<shared_ptr<Binaural::CSingleSourceDSP> >& soundSources,
    vector<SF_INFO>&                                 soundSourcesFileInfo )
{
    // Declaration, initialization and filling mono buffers, one buffer for each source
    CMonoBuffer<float>                    bufferInput( count );

    // Declaration of stereo buffer, used to mix multiple sources in one buffer
    Common::CEarPair<CMonoBuffer<float> > bufferProcessed;

    // loop process audio data sources
    for ( int idx = 0; idx < soundSourcesFileInfo.size( ); idx++ )
    {
        bufferInput.Feed( &data[ idx ][ 0 ], count, soundSourcesFileInfo[ idx ].channels );

        soundSources[ idx ]->SetBuffer( bufferInput );
        soundSources[ idx ]->ProcessAnechoic( bufferProcessed.left, bufferProcessed.right );

        // Adding anechoic processed speech source to the output mix
        bufferOutput.left += bufferProcessed.left;
        bufferOutput.right += bufferProcessed.right;
    }

    /*
     * ROOM REVERB
     */

    // Declaration and initialization of separate buffer needed for the reverb
    Common::CEarPair<CMonoBuffer<float> > bufferReverb;

    // Reverberation processing of all sources
    if ( bEnableReverb )
    {
        environment->ProcessVirtualAmbisonicReverb( bufferReverb.left, bufferReverb.right );
        // Adding reverberated sound to the output mix
        bufferOutput.left += bufferReverb.left;
        bufferOutput.right += bufferReverb.right;
    }

    return 0;
}


int8_t TuneInAudioReverbProcess(
    Common::CEarPair<CMonoBuffer<float> >& bufferOutput,
    float                                  data[][ MAX_BUFFER_LEN ],
    int                                    count,
    int                                    channels )
{
    /*
     * ROOM REVERB
     */

    // Declaration and initialization of separate buffer needed for the reverb
    Common::CEarPair<CMonoBuffer<float> > bufferReverb;

    // Reverberation processing of all sources
    if ( bEnableReverb )
    {
        environment->ProcessVirtualAmbisonicReverb( bufferReverb.left, bufferReverb.right );
        // Adding reverberated sound to the output mix
        bufferOutput.left += bufferReverb.left;
        bufferOutput.right += bufferReverb.right;
    }

    return 0;
}


/*******************************************************************************
 * Function Name: processData( )
 * ******************************************************************************
 * Summary:
 *
 * Parameters:
 *  event: (unused)
 *
 * Return:
 *  None
 *
 *******************************************************************************/
void processData(
    YAML::Node                                            yaml_config,
    Common::CEarPair<CMonoBuffer<float> >&                bufferOutput,
    float                                                 audioData[][ MAX_BUFFER_LEN ],
    int                                                   audioFrameCount,
    vector<shared_ptr<Binaural::CSingleSourceDSP> >&      soundSources,
    vector<SF_INFO>&                                      soundSourcesFileInfo,
    vector<Common::CTransform>&                           soundSourcesPosition,
    std::vector<std::vector<std::vector<std::string> > >& soundSourcesPath,
    std::vector<uint32_t>&                                soundSourcesPathIdx,
    uint64_t                                              totalFrames )
{
    // run audio processing on audioData and get results in bufferOutput

    TuneInAudioProcess( bufferOutput, audioData, audioFrameCount, soundSources, soundSourcesFileInfo );

    // dynamic source's position is set after each buffer computation

    for ( int idx = 0; idx < soundSourcesFileInfo.size( ); idx++ )
    {
        if ( 0 != ( soundSourcesPath[ idx ][ 0 ][ 0 ].compare( "none" ) ) )
        {
            // move only if we have to.
            if ( 100.0f > ( totalFrames * 100.0f / soundSourcesFileInfo[ idx ].frames ) )
            {
                // csvSearchIndex( soundSourcesPath[ idx ], &soundSourcesPathIdx[ idx ], (float) ( totalFrames * 100.0f / soundSourcesFileInfo[ idx ].frames ) );

                uint32_t           nextIdx = soundSourcesPathIdx[ idx ];

                csvSearchNextIndex( soundSourcesPath[ idx ], &nextIdx, (float) ( totalFrames * 100.0f / soundSourcesFileInfo[ idx ].frames ) );

                Common::CTransform nextPosition = soundSourcesPosition[ idx ];

                if ( 0 == csvCoordInterpPosition( soundSourcesPosition[ idx ],     // current source position
                                                  nextPosition,                    // interpolated position
                                                  soundSourcesPath[ idx ],         // CSV path file
                                                  soundSourcesPathIdx[ idx ],      // CSV current idx
                                                  nextIdx,                         // CSV next idx
                                                  totalFrames,
                                                  soundSourcesFileInfo[ idx ].frames ) )
                {
                    ////printf("nextPos,%3.3f,%3.3f,%3.3f\n", nextPosition.GetPosition().x, nextPosition.GetPosition().y, nextPosition.GetPosition().z);

                    soundSources[ idx ]->SetSourceTransform( nextPosition );
                    soundSourcesPosition[ idx ] = nextPosition;
                }

                // update index if needed
                if ( nextIdx > ( 1 + soundSourcesPathIdx[ idx ] ) )
                {
                    soundSourcesPathIdx[ idx ] = 1 + soundSourcesPathIdx[ idx ];
                }
            }
        }
        else
        {
            LOG_MSG( LOG_DEBUG, verbosity, "[ProcessData] IDX: %d, path n.a\n", idx );
        }
    }



#if 0
    // Moving the steps source
    sourcePosition.SetPosition( Common::CVector3( sourcePosition.GetPosition( ).x,
                                                  sourcePosition.GetPosition( ).y - streamTime / 110.0f,
                                                  sourcePosition.GetPosition( ).z > 10 ? sourcePosition.GetPosition( ).z : sourcePosition.GetPosition( ).z + streamTime / 110.0f ) );

    sourceSteps->SetSourceTransform( sourcePosition );
#endif
}


/*******************************************************************************
 * MAIN
 *******************************************************************************/
int main( int argc, char* argv[] )
{
    struct sigaction sigIntHandler;

    /* I/O buffers are of double precision floating point values
     * and will hold our data while we process it.
     */
    static float     data[ MAX_SOURCES ][ MAX_BUFFER_LEN ]; // input data is a mono audio signal for each source
    static float     dataOutBuffer[ MAX_BUFFER_LEN * 2 ];   // ouptut data is a stereo audio signal

    /*
     * Libsnd descriptors and pointers
     */
    SNDFILE*         infile;
    SNDFILE*         outfile;

    SF_INFO          infile_sfinfo;
    SF_INFO          outfile_sfinfo;
    uint64_t         frameCount = 0;
    uint64_t         frameCount_tmp = 0;
    uint64_t         frameCount_max = 0;

    float            source_coord[ 3 ] = { 0.0f };
    uint16_t         sources_cnt = 0;

    /*
     * CLI parameters
     */
    std::string      input_file;
    std::string      output_file;
    std::string      hrtf_sofa_file;
    std::string      brir_sofa_file;
    std::string      params_yaml_file;
    std::string      coord_source = "0,0,1";

    YAML::Node       yaml_config = YAML::Load( _YAML_DEFAULT_CONFIG );

    /*
     * The SF_INFO struct must be initialized before using it.
     */
    memset( &infile_sfinfo,  0, sizeof( infile_sfinfo ) );
    memset( &outfile_sfinfo, 0, sizeof( outfile_sfinfo ) );

    /*
     * install CTRL-C singnal handler
     */
    sigIntHandler.sa_handler = ctrlHandler;
    sigemptyset( &sigIntHandler.sa_mask );
    sigIntHandler.sa_flags = 0;
    sigaction( SIGINT, &sigIntHandler, NULL );


    /*
     * parse CLI parameters
     */
    while ( true )
    {
        const auto opt = getopt_long( argc, argv, short_opts, long_opts, nullptr );

        if ( opt == -1 )
        {
            break;
        }

        switch ( opt )
        {
            case 'i':
                input_file = optarg;
                break;

            case 'o':
                output_file = optarg;
                break;

            case 'p':
                params_yaml_file = optarg;
                break;

            case 'v':
                verbosity = std::atoi( optarg );
                break;

            case 'b':
                iBufferSize = std::atoi( optarg );
                iBufferSize = ( iBufferSize > MAX_BUFFER_LEN ) ? MAX_BUFFER_LEN : iBufferSize;
                break;

            case 's':
                hrtf_sofa_file = optarg;
                break;

            case 'c':
                coord_source = optarg;
                break;

            case 'r':
                brir_sofa_file = optarg;
                bEnableReverb = true;
                break;

            case 'h':
                print_help( );
                return 0;

            case '?': // Unrecognized option
            default:
                print_help( );
                return 1;
        }
    }

    // SANITY CHECK: check yaml params if provided, but command line has precedence on config file
    if ( !( params_yaml_file.empty( ) ) )
    {
        // parse yaml file
        if ( 0 == yamlOpenFile( params_yaml_file, &yaml_config ) )
        {
            LOG_MSG( LOG_LOW, verbosity, "yaml file verified.\n" );
        }
        else
        {
            std::cerr << "Error: cannot read yaml config file. exit.\n\n";
            return 1;
        }
    }

    if ( 0 != setConfigParams( &yaml_config ) )
    {
        std::cerr << "Error: cannot set configuration. exit.\n\n";
        exit( -1 );
    }

    // SANITY CHECK: Check if required arguments are provided
    if ( input_file.empty( ) && params_yaml_file.empty( ) )
    {
        std::cerr << "Error: input file OR yaml_params files must be specified.\n\n";
        print_help( );
        return 1;
    }

    if ( output_file.empty( ) )
    {
        std::cerr << "Error: output file must be specified.\n\n";
        print_help( );
        return 1;
    }

    // SANITY CHECK: hrtf_sofa file is provided
    if ( hrtf_sofa_file.empty( ) && params_yaml_file.empty( ) )
    {
        std::cerr << "Error: hrtf_sofa_file is needed.\n\n";
        print_help( );
        return 1;
    }

    /*
     * CLI oveload: command line parameters will overload config file
     */

    /* overload: input file */
    if ( !( input_file.empty( ) ) )
    {
        yaml_config[ "setup" ][ "sources_count" ] = "1";
        yaml_config[ "setup" ][ "sources" ][ 0 ][ "file_wav" ] = input_file;
        yaml_config[ "setup" ][ "sources" ][ 0 ][ "coord" ] = coord_source;
        yaml_config[ "setup" ][ "sources" ][ 0 ][ "path_csv" ] = "none";
    }

    /* overload: head hrtf file */
    if ( !( hrtf_sofa_file.empty( ) ) )
    {
        yaml_config[ "setup" ][ "head" ][ "hrtf_sofa" ] = hrtf_sofa_file;
    }

    /* overload: room brir file */
    if ( !( brir_sofa_file.empty( ) ) )
    {
        yaml_config[ "setup" ][ "room" ][ "brir_sofa" ] = brir_sofa_file;
    }

    /*
     * decode audio source initial position
     */
    if ( 0 != coordDecode( coord_source, COORD_TYPE_SPHERICAL, source_coord, sizeof( source_coord ) / sizeof( float ), true ) )
    {
        std::cerr << "Error: invalid source coordinates (spherical).\n\n";
        return 1;
    }

    LOG_MSG( LOG_LOW, verbosity,
             "Source Position : %3.2f (azimuth, degree) %3.2f (elevation, degree) %3.2f (distance, metre)\n",
             source_coord[ 0 ], source_coord[ 1 ], source_coord[ 2 ] );

    /*
     * print summary of given params
     */
    print_summary( yaml_config, output_file );

    /*
     * Open Sources input WAV file (mono)
     */
    if ( 0 != openInputFiles( yaml_config, soundSourcesFile, soundSourcesFileInfo, soundSourcesPath, soundSourcesPathIdx, &sources_cnt, MAX_CHANNELS ) )
    {
        return 1;
    }

    /*
     * SANITY CHECK: verify that all sources have the same samplerate
     */
    for ( int idx = 0; idx < soundSourcesFileInfo.size( ); idx++ )
    {
        if ( soundSourcesFileInfo[ 0 ].samplerate != soundSourcesFileInfo[ idx ].samplerate )
        {
            LOG_ERR( LOG_ALWAYS, verbosity, "Error: source .WAV files must have the same samplerate." )
            closeInputFiles( soundSourcesFile );
            exit( 1 );
        }
    }

    /*
     * Open output WAV file (stereo)
     */
    outfile_sfinfo = soundSourcesFileInfo[ 0 ];// infile_sfinfo;
    outfile_sfinfo.channels = 2;
    if ( 0 != openOutputFile( output_file, &outfile, &outfile_sfinfo ) )
    {
        closeInputFiles( soundSourcesFile );
        // sf_close( infile );
        return 1;
    }

    /*
     * 3DTune-In setup
     */
    // if ( 0 != TuneInUserConfig( yaml_config, iBufferSize, infile_sfinfo.samplerate, hrtf_sofa_file, brir_sofa_file ) )
    if ( 0 != TuneInUserConfig( yaml_config, source_coord, iBufferSize ) )
    {
        LOG_ERR( LOG_ALWAYS, verbosity, "Error: cannot configure 3D-TuneIn library." )
        closeInputFiles( soundSourcesFile );
        // sf_close( infile );
        sf_close( outfile );
        return 1;
    }

    // Declaration and initialization of stereo buffer
    outputBufferStereo.left.resize( iBufferSize );
    outputBufferStereo.right.resize( iBufferSize );

    // find the longest of the source tracks
    findSourceMaxLen( yaml_config, soundSourcesFileInfo, &frameCount_max );

    /*
     * Processing LOOP: read audio frames from the input file,
     * process audio data and write them to the output file.
     */

    progressbar bar( frameCount_max / iBufferSize );

    // while ( ( frameCount = (int) sf_read_float( infile, data, iBufferSize ) ) && ( !bCtrlExit ) )
    uint64_t    totalFrames = 0;
    while ( ( totalFrames < frameCount_max ) && ( !bCtrlExit ) )
    {
        if ( ( verbosity < 20 ) && ( verbosity > 0 ) )
        {
            bar.update( );
        }

        /* read frames from all streams, track max frame len */
        uint64_t             frameCount_tmp_max = 0;
        for ( int idx = 0; idx < sources_cnt; idx++ )
        {
            frameCount_tmp = (int) sf_read_float( soundSourcesFile[ idx ], &data[ idx ][ 0 ], iBufferSize );

            /* tail erasing if needed */
            if ( frameCount_tmp < iBufferSize )
            {
                memset( &data[ idx ][ 0 ] + frameCount_tmp * sizeof( float ), 0, ( MAX_BUFFER_LEN - frameCount_tmp ) * sizeof( float ) );
            }

            /* track max framecnt of the source vector */
            if ( frameCount_tmp > frameCount_tmp_max )
            {
                frameCount_tmp_max = frameCount_tmp;
            }
        }

        /* here is the max framecount for all opened sources */
        frameCount = frameCount_tmp_max;

        // clear buffer with zeros
        outputBufferStereo.left.Fill( iBufferSize, 0.0f );
        outputBufferStereo.right.Fill( iBufferSize, 0.0f );

        processData( yaml_config, outputBufferStereo, data, frameCount,
                     soundSources, soundSourcesFileInfo, soundSourcesPosition,
                     soundSourcesPath, soundSourcesPathIdx,
                     totalFrames );

        totalFrames += frameCount;
        LOG_MSG( LOG_DEBUG, verbosity, "frameCount %" PRIu64 " [%" PRIu64 "]\n", totalFrames, frameCount_max );

        // Stereo buffer for correct stereo output
        CStereoBuffer<float> iOutput;

        // interlace the dual-mono OutputBuffer into our Stereo sequencial buffer
        iOutput.Interlace( outputBufferStereo.left, outputBufferStereo.right );

        // vector to array: loop to fill values
        // ToDo: can we optimize with memcpy?
        float*               dataOut = &dataOutBuffer[ 0 ];

        for ( auto it = iOutput.begin( ); it != iOutput.end( ); it++ )
        {
            dataOut[ 0 ] = *it;             // Setting of value in actual buffer position
            dataOut = &dataOut[ 1 ];        // Updating pointer to next buffer position
        }

        sf_write_float( outfile, dataOutBuffer, frameCount * 2 );
    }

    /* Close input and output files. */
    closeInputFiles( soundSourcesFile );
    // sf_close( infile );
    sf_close( outfile );


    // Informing user by the console to press any key to end the execution
    LOG_MSG( LOG_LOW,    verbosity, "done. \n" );
    LOG_MSG( LOG_ALWAYS, verbosity, "\n" );

    return 0;
} // main


/* EOF */
