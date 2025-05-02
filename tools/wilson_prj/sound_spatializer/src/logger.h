/*
 * $ Copyright Broadcom Corporation $
 */

/**
 * @file logger.h
 *
 * logging macros for console output. These macros will be disabled when building
 * in RELEASE mode so that the code from printf is NOT part of the binary app.
 *
 */
#ifndef _H_LOGGER_H_
#define _H_LOGGER_H_

#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>
#include <stdint.h>


#define LOG_ZERO    ((uint8_t)(0))
#define LOG_ALWAYS  ((uint8_t)(0))
#define LOG_MIN     ((uint8_t)(10))
#define LOG_DEFAULT ((uint8_t)(20))
#define LOG_LOW     ((uint8_t)(20))
#define LOG_MEDIUM  ((uint8_t)(30))
#define LOG_HIGH    ((uint8_t)(40))
#define LOG_DEBUG   ((uint8_t)(50))
#define LOG_ALL     ((uint8_t)(90))
#define LOG_MAX     ((uint8_t)(255))


typedef struct log_
{
    FILE * log_file;
} log_t;


// #if (NDEBUG)

// /*
//  * FLAG that tells the status of the LOGGER
//  */
// #define LOGGER_ENABLED (0)

// /*
//  * EMPTY wrapping macros
//  */
// #define LOG_MSG(log_lvl, verbose, ...) {}
// #define LOG_ERR(log_lvl, verbose, ...) {}
// #define LOG_PRINTF(...){}

// #else //_DEBUG

/*
 * FLAG that tells the status of the LOGGER
 */
#define LOGGER_ENABLED (1)

/*
 * WRAPPING macros
 */

#define LOG_MSG(log_lvl, verbosity, ...)                 \
    do                                                 \
    {                                                  \
        if ((verbosity) >= (log_lvl)){                   \
            fprintf(stdout,__VA_ARGS__);               \
        }                                              \
    } while (0);

#define LOG_ERR(log_lvl, verbosity, ...)                 \
    do                                                 \
    {                                                  \
        if ((verbosity) >= (log_lvl)){                   \
            fprintf(stderr,__VA_ARGS__);               \
        }                                              \
    } while (0);

#define LOG_PRINTF(...)                                \
    do                                                 \
    {                                                  \
            fprintf(stdout,__VA_ARGS__);               \
    } while (0);

// #endif /* NDEBUG */


#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* _H_LOGGER_H_ */
