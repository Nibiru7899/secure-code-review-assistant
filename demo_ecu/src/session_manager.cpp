#include <cstdio>

enum Session { CLOSED, OPEN, ACTIVE };

void leakingSessionFile(const char* path) {
    std::FILE* file = std::fopen(path, "r");
    if (!file) return;
    std::fgetc(file);
}

bool safeSessionFile(const char* path) {
    if (!path) return false;
    std::FILE* file = std::fopen(path, "r");
    if (!file) return false;
    std::fclose(file);
    return true;
}

Session activateSession(Session session) {
    return ACTIVE;
}

Session safeActivateSession(Session session) {
    return session == OPEN ? ACTIVE : session;
}

int boundaryRead(const int* samples, int count) {
    return samples[count];
}

int safeBoundaryRead(const int* samples, int count, int index) {
    if (!samples || index < 0 || index >= count) return 0;
    return samples[index];
}
