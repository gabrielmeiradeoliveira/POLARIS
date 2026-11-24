package main

import (
	"flag"
	"fmt"
	"os"
	"runtime"
	"runtime/debug"

	"github.com/polaris-sec/polaris-scanner/internal/contract"
	"github.com/polaris-sec/polaris-scanner/internal/walker"
)

const ScannerVersion = "2.7.0"

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: polaris-scanner <analyze|doctor> [flags]")
		os.Exit(2)
	}

	cmd := os.Args[1]
	fs := flag.NewFlagSet(cmd, flag.ExitOnError)
	target := fs.String("target", ".", "Target directory")
	project := fs.String("project", "default", "Project key")
	branch := fs.String("branch", "main", "Branch name")
	_ = fs.String("target-branch", "", "Base branch for PR diff")
	_ = fs.String("pr-key", "", "Pull Request identifier")
	_ = fs.String("coverage-report", "", "Coverage report path")
	profile := fs.String("profile", "balanced", "Resource profile: low-spec|balanced|max")
	format := fs.String("format", "json", "Output format: json|sarif")
	_ = fs.Bool("no-cache", false, "Disable incremental SHA-256 cache")
	_ = fs.String("sbom-out", "", "Optional CycloneDX SBOM output path")
	_ = fs.Parse(os.Args[2:])

	if *profile == "low-spec" {
		debug.SetMemoryLimit(160 * 1024 * 1024)
		debug.SetGCPercent(50)
		if runtime.NumCPU() > 2 {
			runtime.GOMAXPROCS(2)
		}
	}

	if cmd == "doctor" {
		fmt.Printf(`{"status":"OK","scanner":"polaris-scanner-go","version":%q,"profile":%q}`+"\n", ScannerVersion, *profile)
		return
	}

	files, err := walker.Walk(*target)
	if err != nil {
		fmt.Fprintf(os.Stderr, "walk error: %v\n", err)
		os.Exit(1)
	}

	report := contract.NewReport(*project, *branch, ScannerVersion, len(files))
	if *format == "sarif" {
		fmt.Println(contract.ToSARIF(report))
		return
	}
	fmt.Println(contract.ToJSON(report))
}
