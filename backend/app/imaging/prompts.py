# backend/app/imaging/prompts.py
"""English prompt templates per image-edit operation; the user's own text is appended at the end."""

OPERATIONS = ("merge_people", "enhance", "remove_background", "outpaint", "custom")

TEMPLATES = {
    "merge_people": (
        "Combine the people from all {n} input photos into ONE realistic group photo. Keep every person's face, "
        "hairstyle, skin tone, body proportions and clothes clearly recognisable and unchanged. Use one consistent, "
        "natural lighting and perspective, a plausible shared background, and add no new people and no extra "
        "limbs. Output a single image."
    ),
    "enhance": (
        "Enhance the input image: better exposure, colour balance, sharpness and noise reduction. Do not change "
        "what is in the picture, do not alter faces or add or remove objects. Output a single image."
    ),
    "remove_background": (
        "Remove the background of the input image: keep the main subject exactly as it is and place it on a "
        "plain, clean, uniform light background. Output a single image."
    ),
    "outpaint": (
        "Extend the input image beyond its borders (outpainting): continue the scene naturally in the same "
        "style, lighting and perspective, keep the original content unchanged. Output a single image."
    ),
    "custom": "Edit the input image(s) as the user instruction says. Output a single image.",
}


def build_prompt(operation: str, instruction: str, n_images: int) -> str:
    """The full text sent with the images; `operation` must be one of OPERATIONS."""
    return f"{TEMPLATES[operation].format(n=n_images)}\n\nUser instruction: {instruction.strip()}"
