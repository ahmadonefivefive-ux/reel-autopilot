import py_compile
for f in ["config.py", "topic_finder.py", "script_writer.py", "stickman_art.py", "stickman.py",
          "upload.py", "video_assembly.py", "voiceover.py", "thumbnail.py", "topics_util.py", "run_pipeline.py"]:
    py_compile.compile(f, doraise=True)
print("COMPILE-OK")
