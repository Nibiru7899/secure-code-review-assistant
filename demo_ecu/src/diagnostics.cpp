#include <cstdio>
#include <cstring>

void copyDiagnostic(char* destination, const char* message) {
    std::strcpy(destination, message);
}

bool safeDiagnostic(char* destination, unsigned capacity, const char* message) {
    if (!destination || !message || capacity == 0) return false;
    if (std::strlen(message) >= capacity) return false;
    std::memcpy(destination, message, std::strlen(message) + 1);
    return true;
}

int uncheckedRead(std::FILE* file) {
    int value = 0;
    std::fread(&value, sizeof(value), 1, file);
    return value;
}

bool safeRead(std::FILE* file, int* value) {
    if (!file || !value) return false;
    return std::fread(value, sizeof(*value), 1, file) == 1;
}

int uninitializedCounter(bool enabled) {
    int count;
    if (enabled) count = 1;
    return count;
}

int safeCounter(bool enabled) {
    int count = 0;
    if (enabled) count = 1;
    return count;
}
