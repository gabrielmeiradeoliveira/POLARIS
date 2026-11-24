package runner

import (
	"context"
	"os/exec"
)

type DeepWorkerPool struct {
	sem chan struct{}
}

func NewDeepWorkerPool(lowSpec bool) *DeepWorkerPool {
	limit := 4
	if lowSpec {
		limit = 1
	}
	return &DeepWorkerPool{sem: make(chan struct{}, limit)}
}

func (p *DeepWorkerPool) RunLazy(ctx context.Context, files []string, cmdName string, args ...string) ([]byte, error) {
	if len(files) == 0 {
		return nil, nil
	}
	p.sem <- struct{}{}
	defer func() { <-p.sem }()
	cmd := exec.CommandContext(ctx, cmdName, append(args, files...)...)
	return cmd.CombinedOutput()
}
