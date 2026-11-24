package gitdiff

import (
	"os/exec"
	"strings"
)

func ChangedFiles(repoDir, baseBranch string) ([]string, error) {
	cmd := exec.Command("git", "-C", repoDir, "diff", "--name-only", baseBranch+"...HEAD")
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	var files []string
	for _, line := range strings.Split(string(out), "\n") {
		trimmed := strings.TrimSpace(line)
		if trimmed != "" {
			files = append(files, trimmed)
		}
	}
	return files, nil
}
