#
#
#

WATERMARK="Photo: Andrew Schmadel"

if [ `ls -a | grep .jpg.original | wc -l` -gt 0 ]
then
    echo "Backup files already exist!"
    echo "Clean those out (to make sure we don't overwrite originals) before continuing"
    echo 'Try: for i in `ls -a | grep .original`; do rm $i; done'
    echo "Or, if you want to restore the originals:"
    echo 'for i in `ls -a | grep .original`; do mv $i `echo $i | sed ''s/.\(.*\).jpg.original/\1.jpg/''`; done'
    exit
fi

echo "Backing up jpg files to .*.jpg.original"
for i in *.jpg
do
    cp "$i" ".$i.original"
done

echo "Watermarking all .jpg files."
for i in *.jpg;
do
    echo " - $i"
    convert $i -fill white -font Brush-Script-MT-Italic \
        -pointsize 22 -gravity SouthEast\
        -annotate 0 "$WATERMARK" $i
done

echo "Done!"
