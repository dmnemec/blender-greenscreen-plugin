bl_info = {
    "name": "Greenscreen AI Data Prep",
    "author": "Gemini Code Assist",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Greenscreen",
    "description": "Initial settings for Greenscreen AI Data Prep project",
    "category": "System",
}

import bpy

class GREENSCREEN_OT_setup(bpy.types.Operator):
    """Configure initial settings for Greenscreen AI Data Prep"""
    bl_idname = "greenscreen.setup_project"
    bl_label = "Initialize Project Settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        # 1. Set Render Engine to Eevee (Optimized for speed in data prep)
        scene.render.engine = 'BLENDER_EEVEE'

        # 2. Set Resolution to 2048x2048 (Standard for AI datasets)
        scene.render.resolution_x = 2048
        scene.render.resolution_y = 2048
        scene.render.resolution_percentage = 100

        # 3. Set Color Management to Standard
        # This ensures that the green background is rendered as pure (0, 1, 0)
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0

        # 4. Set Output Format to PNG RGBA
        scene.render.image_settings.file_format = 'OPEN_EXR'  # Use OpenEXR for lossless RGBA output
        scene.render.image_settings.color_mode = 'RGBA' # Ensure alpha channel is included
        scene.render.image_settings.color_depth = '32' # Use 32-bit for maximum precision in AI data prep
        #TODO add codec DWAB, Quality 90%
        scene.render.image_settings.quality = 100
        scene.render.image_settings.exr_codec = 'DWAB'

        # 5. Setup World Background (Pure Green Screen)
        if not scene.world:
            new_world = bpy.data.worlds.new("GreenscreenWorld")
            scene.world = new_world
        
        scene.world.use_nodes = True
        nodes = scene.world.node_tree.nodes
        nodes.clear()
        
        node_background = nodes.new(type='ShaderNodeBackground')
        node_background.inputs[0].default_value = (0.0, 1.0, 0.0, 1.0)  # Pure Green
        node_background.inputs[1].default_value = 1.0  # Strength
        
        node_output = nodes.new(type='ShaderNodeOutputWorld')
        
        links = scene.world.node_tree.links
        links.new(node_background.outputs[0], node_output.inputs[0])

        # 6. Disable Film Transparency to ensure the green background renders
        scene.render.film_transparent = False

        self.report({'INFO'}, "Greenscreen AI Data Prep settings applied.")
        return {'FINISHED'}

class GREENSCREEN_PT_panel(bpy.types.Panel):
    """Panel for Greenscreen AI Data Prep"""
    bl_label = "Greenscreen AI Data Prep"
    bl_idname = "GREENSCREEN_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Greenscreen'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Project Initialization")
        layout.operator("greenscreen.setup_project", icon='PREFERENCES')

def register():
    bpy.utils.register_class(GREENSCREEN_OT_setup)
    bpy.utils.register_class(GREENSCREEN_PT_panel)

def unregister():
    bpy.utils.unregister_class(GREENSCREEN_OT_setup)
    bpy.utils.unregister_class(GREENSCREEN_PT_panel)

if __name__ == "__main__":
    register()
