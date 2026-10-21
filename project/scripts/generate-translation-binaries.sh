set -e

# Compile every .po catalog into a binary .mo catalog.
#
# The conversions are independent of each other, and most of the old
# sequential loop's wall clock went to process start-up rather than to the
# conversion itself, so they now run in bounded parallel batches.  The .mo
# files produced are byte-identical to the sequential loop's output, the
# locale names are still echoed in sorted order so CI logs stay diffable, and
# a broken catalog still stops the run instead of being skipped.
#
# JOBS caps the batch width: a 2-core CI runner should not be asked to start
# 36 compilers at once, and past 8 the wall clock stops improving.

JOBS="${JOBS:-8}"
batch=""
running=0
failed=0

reap() {
    for pid in $batch; do
        wait "$pid" || failed=1
    done
    batch=""
    running=0
    if [ "$failed" -ne 0 ]; then
        echo "translation compilation failed" >&2
        exit 1
    fi
}

for d in src/humanize/locale/*/; do
    locale="$(basename $d)"
    echo "$locale"
    # compile to binary .mo
    msgfmt --check -o "src/humanize/locale/$locale/LC_MESSAGES/humanize.mo" \
        "src/humanize/locale/$locale/LC_MESSAGES/humanize.po" &
    batch="$batch $!"
    running=$((running + 1))
    if [ "$running" -ge "$JOBS" ]; then
        reap
    fi
done
reap
