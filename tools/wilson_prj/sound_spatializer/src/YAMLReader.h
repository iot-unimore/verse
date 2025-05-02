#ifndef THREAD_SAFE_YAML_READER_H
#define THREAD_SAFE_YAML_READER_H

#include <iostream>
#include <fstream>
#include <memory>
#include <string>
#include <mutex>
#include <yaml-cpp/yaml.h>
#include <functional>

namespace yaml {

class YAMLReader {
public:
    // Reads the YAML file and parses it into a YAML node
    static bool readYAML(const std::string& filePath, YAML::Node& root) {
        std::lock_guard<std::mutex> lock(mutex_);  // Lock to ensure thread safety

        try {
            std::ifstream file(filePath);
            if (!file.is_open()) {
                std::cerr << "Error opening file: " << filePath << std::endl;
                return false;
            }

            root = YAML::Load(file);
            if (root.IsNull()) {
                std::cerr << "Error: Failed to parse YAML file." << std::endl;
                return false;
            }
        } catch (const std::exception& e) {
            std::cerr << "Error reading YAML file: " << e.what() << std::endl;
            return false;
        }

        return true;
    }

    // Parses the YAML file row by row and calls a handler function for each node
    static bool readYAMLRowByRow(const std::string& filePath,
                                  std::function<void(const YAML::Node&)> nodeHandler) {
        std::lock_guard<std::mutex> lock(mutex_);  // Lock to ensure thread safety

        try {
            std::ifstream file(filePath);
            if (!file.is_open()) {
                std::cerr << "Error opening file: " << filePath << std::endl;
                return false;
            }

            YAML::Node root = YAML::Load(file);
            if (root.IsNull()) {
                std::cerr << "Error: Failed to parse YAML file." << std::endl;
                return false;
            }

            // Iterate through all the elements in the root YAML node
            traverseYAMLNode(root, nodeHandler);  // Use helper function to traverse
        } catch (const std::exception& e) {
            std::cerr << "Error reading YAML file: " << e.what() << std::endl;
            return false;
        }

        return true;
    }

    // Helper function to traverse YAML nodes (recursive)
    static void traverseYAMLNode(const YAML::Node& node,
                                  std::function<void(const YAML::Node&)> nodeHandler) {
        if (node.IsNull()) {
            return;
        }

        // If the node is a Map (key-value pairs)
        if (node.IsMap()) {
            for (const auto& item : node) {
                if (item.first.IsScalar()) {
                    ////std::string key = item.first.as<std::string>();  // Safely convert the key to a string
                    ////std::cout << "Processing Map - Key: " << key << std::endl;

                    // Handle the value (item.second)
                    nodeHandler(item.second);

                    // Recursively process the value (item.second) in case it's a nested structure (map or sequence)
                    traverseYAMLNode(item.second, nodeHandler);
                } else {
                    std::cerr << "Non-scalar key found in map!" << std::endl;
                }

#if 0
                // Debugging output for the value type
                if (item.second.IsScalar()) {
                    std::cout << "Map - Key: " << item.first.as<std::string>() 
                              << ", Value: " << item.second.as<std::string>() << std::endl;
                } else if (item.second.IsMap()) {
                    std::cout << "Map - Key: " << item.first.as<std::string>()
                              << ", Value is a nested map." << std::endl;
                } else if (item.second.IsSequence()) {
                    std::cout << "Map - Key: " << item.first.as<std::string>()
                              << ", Value is a sequence." << std::endl;
                }
#endif
            }
        }
        // If the node is a Sequence (array of values)
        else if (node.IsSequence()) {
            ////std::cout << "Processing Sequence:" << std::endl;
            for (const auto& item : node) {
                // Handle the item (sequence element)
                nodeHandler(item);

                // Recursively process the item (if it's a nested structure)
                traverseYAMLNode(item, nodeHandler);
            }
        }
        // Handle scalar values (strings, numbers, etc.)
        else if (node.IsScalar()) {
            try {
                // Safely check if the node is a string
                if (node.Type() == YAML::NodeType::Scalar) {
                    ////std::string value = node.as<std::string>();  // Safely convert scalar to string
                    ////std::cout << "Processing Scalar: " << value << std::endl;
                    nodeHandler(node);  // Call the handler on the scalar value
                } else {
                    std::cerr << "Unexpected node type encountered during scalar handling!" << std::endl;
                }
            } catch (const YAML::TypedBadConversion<std::string>& e) {
                std::cerr << "Error: Invalid conversion to string. Node type might not be a string." << std::endl;
            }
        } else {
            std::cerr << "Unknown node type encountered!" << std::endl;
        }
    }

private:
    // Mutex to ensure thread safety
    static inline std::mutex mutex_;
};

}  // namespace yaml

#endif  // THREAD_SAFE_YAML_READER_H
