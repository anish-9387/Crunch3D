import sys
import json
import argparse
import traceback

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--preserve-normals", action="store_true")
    parser.add_argument("--preserve-boundaries", action="store_true")
    parser.add_argument("--generate-lods", action="store_true")
    parser.add_argument("--strict-quality", action="store_true")
    parser.add_argument("--out-dir", type=str, required=True)
    parser.add_argument("--base-name", type=str, required=True)
    parser.add_argument("--out-ext", type=str, required=True)
    parser.add_argument("--original-faces", type=int, required=True)
    parser.add_argument("--max-dev", type=float, default=2.0)
    parser.add_argument("--max-over", type=float, default=12.0)
    
    args = parser.parse_args()
    
    try:
        # Prevent OpenMP conflicts on MacOS/Linux between PyMeshLab and PyTorch
        import os
        os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
        try:
            import torch
            _ = torch.tensor([1.0])
        except ImportError:
            pass

        from model.engine.mesh_optimizer import decimate_mesh, generate_lods
        
        optimized_stats, quality_meta = decimate_mesh(
            input_path=args.input,
            output_path=args.output,
            target_faces=args.target,
            preserve_normals=args.preserve_normals,
            preserve_boundaries=args.preserve_boundaries,
            strict_quality=args.strict_quality,
            max_deviation_percent=args.max_dev,
            max_target_overshoot_percent=args.max_over,
        )
        
        lod_results = None
        if args.generate_lods:
            lod_results = generate_lods(
                input_path=args.input,
                output_dir=args.out_dir,
                base_name=args.base_name,
                original_faces=args.original_faces,
                output_extension=args.out_ext,
                preserve_normals=args.preserve_normals,
                preserve_boundaries=args.preserve_boundaries,
            )
            
        print(json.dumps({
            "status": "success",
            "optimized_stats": optimized_stats.model_dump() if hasattr(optimized_stats, "model_dump") else optimized_stats.dict(),
            "quality_meta": quality_meta,
            "lod_results": [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in lod_results] if lod_results else None
        }))
        
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }))
        sys.exit(1)

if __name__ == "__main__":
    main()
