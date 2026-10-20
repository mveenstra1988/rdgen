// Build a macOS .dmg from the staged VIT AI Hub.app (works on Linux CI).
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	dmg "github.com/jetbrains/go-dmg-writer"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Fprintf(os.Stderr, "usage: build-dmg <stage-dir-with-app> <out.dmg>\n")
		os.Exit(2)
	}
	src := os.Args[1]
	out := os.Args[2]
	if st, err := os.Stat(src); err != nil || !st.IsDir() {
		fmt.Fprintf(os.Stderr, "stage dir missing: %s\n", src)
		os.Exit(1)
	}
	_ = os.Remove(out)
	_ = os.MkdirAll(filepath.Dir(out), 0o755)

	w := &dmg.DMG{
		VolumeName: "VIT AI Hub",
		Time:       time.Date(2026, 10, 19, 12, 0, 0, 0, time.UTC),
		OwnerID:    dmg.OwnerIDUnset,
		GroupID:    dmg.OwnerIDUnset,
	}
	if err := w.Create(src, out, dmg.ModeReadOnlyCompressed); err != nil {
		fmt.Fprintf(os.Stderr, "dmg create failed: %v\n", err)
		os.Exit(1)
	}
	fi, _ := os.Stat(out)
	fmt.Printf("DMG: %s (%d bytes)\n", out, fi.Size())
}
