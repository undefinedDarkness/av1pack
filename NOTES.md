Highest quality h264 nvenv:
ffmpeg -i INPUT_NAME -c:v h264_nvenc -qp 15 -profile:v high444p -pix_fmt yuv444p -tune hq -preset p7 -rc constqp -rc-lookahead 32 OUTPUT_NAME (qp 15 is visually lossless)