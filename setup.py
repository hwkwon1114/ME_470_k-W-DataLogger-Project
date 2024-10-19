import os
import shutil

def setup_project():
    """Setup and verify project structure"""
    # Create directories
    directories = [
        'app/templates',
        'app/static/css',
        'instance'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created/verified directory: {directory}")
    
    # Verify template file
    template_path = 'app/templates/dashboard.html'
    if not os.path.exists(template_path):
        print(f"ERROR: Missing template file at {template_path}")
        return False
    
    # Verify CSS file
    css_path = 'app/static/css/style.css'
    if not os.path.exists(css_path):
        print(f"ERROR: Missing CSS file at {css_path}")
        return False
    
    print("Project structure verified successfully!")
    return True

if __name__ == "__main__":
    setup_project()