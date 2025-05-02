#ifndef THREAD_SAFE_CSV_READER_H
#define THREAD_SAFE_CSV_READER_H

#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>

namespace csv {

class CSVReader {
public:
    // Read the CSV file and return its rows as a vector of vectors of strings
    static bool readCSV(const std::string& filePath, std::vector<std::vector<std::string>>& result) {
        std::lock_guard<std::mutex> lock(mutex_);
        result.clear();

        std::ifstream file(filePath);
        if (!file.is_open()) {
            std::cerr << "Error opening file: " << filePath << std::endl;
            return false;
        }

        std::string line;
        while (std::getline(file, line)) {
            std::vector<std::string> row;
            std::stringstream ss(line);
            std::string cell;
            while (std::getline(ss, cell, ',')) {
                row.push_back(cell);
            }

            // skip comments starting with "#"
            if(row[0][0] != '#')
            {
                result.push_back(row);
            }
            else
            {
                cout << "skip line: " << row[0] << std::endl;
            }
        }

        file.close();
        return true;
    }

    // Read a CSV file row by row (reentrant and thread-safe)
    static bool readCSVRowByRow(const std::string& filePath, 
                                std::function<void(const std::vector<std::string>&)> rowHandler) {
        std::lock_guard<std::mutex> lock(mutex_); 

        std::ifstream file(filePath);
        if (!file.is_open()) {
            std::cerr << "Error opening file: " << filePath << std::endl;
            return false;
        }

        std::string line;
        while (std::getline(file, line)) {
            std::vector<std::string> row;
            std::stringstream ss(line);
            std::string cell;
            while (std::getline(ss, cell, ',')) {
                row.push_back(cell);
            }

            // Call the provided rowHandler function for each row (reentrant behavior)
            rowHandler(row);
        }

        file.close();
        return true;
    }

private:
    // Mutex to ensure thread-safety
    static inline std::mutex mutex_;
};

} // namespace csv

#endif // THREAD_SAFE_CSV_READER_H


/* EXAMPLE:

#include "CSVReader.h"
#include <iostream>

void processRow(const std::vector<std::string>& row) {
    // For demonstration, just print the row to the console
    for (const auto& cell : row) {
        std::cout << cell << " ";
    }
    std::cout << std::endl;
}

int main() {
    // Example: Read the entire CSV into memory
    std::vector<std::vector<std::string>> data;
    if (csv::CSVReader::readCSV("example.csv", data)) {
        std::cout << "CSV file read successfully!" << std::endl;
    } else {
        std::cerr << "Failed to read the CSV file!" << std::endl;
    }

    // Example: Read the CSV row by row and process each row
    if (csv::CSVReader::readCSVRowByRow("example.csv", processRow)) {
        std::cout << "CSV rows processed successfully!" << std::endl;
    } else {
        std::cerr << "Failed to process the CSV file row by row!" << std::endl;
    }

    return 0;
}
*/
