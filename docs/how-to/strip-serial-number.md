# Strip serial number

Videos recorded on some drones may contain the aircraft serial number in their
metadata. The embedder itself does not add this information, but you can remove
existing serial numbers with `exiftool` before publishing your footage.

```bash
exiftool -DroneSerialNumber= -overwrite_original *.MP4
```

Run the command in the directory containing the video files. The option
`-overwrite_original` updates the files in place.
