package walker

import (
	"io/fs"
	"path/filepath"
	"strings"
)

var defaultIgnoredDirs = map[string]bool{
	".git": true, ".venv": true, "node_modules": true,
	"bin": true, "obj": true, "target": true, "build": true, "dist": true,
}

func Walk(root string) ([]string, error) {
	var files []string
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			if defaultIgnoredDirs[d.Name()] {
				return filepath.SkipDir
			}
			return nil
		}
		if !strings.HasPrefix(d.Name(), ".") {
			files = append(files, path)
		}
		return nil
	})
	return files, err
}
