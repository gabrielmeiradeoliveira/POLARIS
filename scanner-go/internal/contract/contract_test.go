package contract

import "testing"

func TestCompressAndSign(t *testing.T) {
	gz, sig, err := CompressAndSign([]byte(`{"ok":true}`), "secret")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(gz) == 0 || len(sig) != 64 {
		t.Fatalf("invalid gzip/signature output")
	}
}
