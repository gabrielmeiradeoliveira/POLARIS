package cache

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
)

type Entry struct {
	FileSHA256 string `json:"file_sha256"`
	IssuesJSON string `json:"issues_json"`
}

type Store struct {
	mu      sync.RWMutex
	path    string
	entries map[string]Entry
}

func Open(path string) (*Store, error) {
	s := &Store{path: path, entries: make(map[string]Entry)}
	if data, err := os.ReadFile(path); err == nil {
		_ = json.Unmarshal(data, &s.entries)
	}
	return s, nil
}

func MakeKey(fileSHA256, profileHash, scannerVersion, depsHash string) string {
	h := sha256.Sum256([]byte(fileSHA256 + ":" + profileHash + ":" + scannerVersion + ":" + depsHash))
	return hex.EncodeToString(h[:])
}

func (s *Store) Get(key string) (Entry, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	e, ok := s.entries[key]
	return e, ok
}

func (s *Store) Put(key string, e Entry) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.entries[key] = e
}

func (s *Store) Save() error {
	s.mu.RLock()
	defer s.mu.RUnlock()
	if err := os.MkdirAll(filepath.Dir(s.path), 0o755); err != nil {
		return err
	}
	b, err := json.Marshal(s.entries)
	if err != nil {
		return err
	}
	return os.WriteFile(s.path, b, 0o644)
}
