bl_info = {
    "name": "Greenscreen AI Data Prep",
    "author": "Gemini Code Assist",
    "version": (1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Greenscreen",
    "description": "Initial settings for Greenscreen AI Data Prep project",
    "category": "System",
}

import bpy
import os

class GREENSCREEN_OT_setup(bpy.types.Operator):
    """Configure initial settings for Greenscreen AI Data Prep"""
    bl_idname = "greenscreen.setup_project"
    bl_label = "Initialize Project Settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        # 1. Set Render Engine to Eevee (Optimized for speed in data prep)
        scene.render.engine = 'BLENDER_EEVEE'

        # 2. Set Frame Range (Exactly 48 frames per styleguide)
        scene.frame_start = 1
        scene.frame_end = 48

        # 3. Set Resolution to 2048x2048 (Standard for AI datasets)
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
        scene.render.image_settings.quality = 90 # DWAB compression quality
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

class GREENSCREEN_OT_setup_passes(bpy.types.Operator):
    """Setup render passes and output nodes for export"""
    bl_idname = "greenscreen.setup_passes"
    bl_label = "Setup Render Passes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene

        # 0. Check if file is saved to determine base path
        if not bpy.data.is_saved:
            self.report({'WARNING'}, "Save your .blend file first to enable automatic folder incrementing.")
            return {'CANCELLED'}
        
        # 1. Ensure View Layers exist for specific passes
        if "FG" not in scene.view_layers:
            scene.view_layers.new(name="FG")
        if "BG" not in scene.view_layers:
            scene.view_layers.new(name="BG")
        
        # 2. Enable Compositing Nodes
        scene.use_nodes = True
        
        # Blender 5.0 API: node_tree is removed from Scene, replaced by compositing_node_group.
        # We ensure it is initialized programmatically if use_nodes didn't create it.
        tree = scene.compositing_node_group
        if tree is None:
            # Initialize a new compositor node group and assign it to the scene
            tree = bpy.data.node_groups.new("CompositingNodeTree", "CompositorNodeTree")
            scene.compositing_node_group = tree
            
        nodes = tree.nodes
        links = tree.links
        nodes.clear()
        
        # 3. Create Render Layer Nodes for each pass
        rl_input = nodes.new('CompositorNodeRLayers')
        rl_input.layer = "ViewLayer"
        rl_input.location = (0, 400)
        
        rl_fg = nodes.new('CompositorNodeRLayers')
        rl_fg.layer = "FG"
        rl_fg.location = (0, 100)
        
        rl_bg = nodes.new('CompositorNodeRLayers')
        rl_bg.layer = "BG"
        rl_bg.location = (0, -200)
        
        # 4. Determine next Clip folder name (Automatic Increment)
        base_dir = os.path.dirname(bpy.data.filepath)
        clip_index = 1
        while os.path.exists(os.path.join(base_dir, f"Clip{clip_index:04d}")):
            clip_index += 1
        clip_name = f"Clip{clip_index:04d}"
        
        # Physically create the directory structure to avoid render errors
        clip_path = os.path.join(base_dir, clip_name)
        os.makedirs(clip_path, exist_ok=True)

        # 5. Setup File Output Node
        file_output = nodes.new('CompositorNodeOutputFile')
        file_output.location = (600, 100)
        # Blender 5.0 API: base_path renamed to directory
        file_output.directory = "//" + clip_name + "/"
        
        # Ensure node uses styleguide EXR settings
        file_output.format.file_format = 'OPEN_EXR'
        file_output.format.exr_codec = 'DWAB'
        file_output.format.color_depth = '32'
        
        # 6. Configure File Output Slots (Styleguide Directory Structure)
        # Blender 5.0 API: file_slots removed, replaced by file_output_items
        file_output.file_output_items.clear()
        
        # Input/ (Foreground on greenscreen)
        item_input = file_output.file_output_items.new("Input")
        item_input.path = "Input/render_"
        links.new(rl_input.outputs['Image'], file_output.inputs[0])
        
        # FG/ (Foreground on black/neutral)
        item_fg = file_output.file_output_items.new("FG")
        item_fg.path = "FG/render_"
        links.new(rl_fg.outputs['Image'], file_output.inputs[1])
        
        # BG/ (Background only)
        item_bg = file_output.file_output_items.new("BG")
        item_bg.path = "BG/render_"
        links.new(rl_bg.outputs['Image'], file_output.inputs[2])

        # Alpha/ (Foreground alpha only)
        item_alpha = file_output.file_output_items.new("Alpha")
        item_alpha.path = "Alpha/render_"
        # We pull Alpha from the main Input layer
        links.new(rl_input.outputs['Alpha'], file_output.inputs[3])

        self.report({'INFO'}, f"Configured for {clip_name}")
        return {'FINISHED'}

class GREENSCREEN_OT_render_clip(bpy.types.Operator):
    """Trigger the animation render for the current clip"""
    bl_idname = "greenscreen.render_clip"
    bl_label = "Render Animation Clip"
    bl_options = {'REGISTER'}

    def execute(self, context):
        # Triggers the render animation (Ctrl+F12)
        bpy.ops.render.render(animation=True)
        self.report({'INFO'}, "Render started. Check the Clip folder for output.")
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
        layout.separator()
        layout.label(text="Export Configuration")
        layout.operator("greenscreen.setup_passes", icon='RENDER_RESULT')
        layout.separator()
        layout.label(text="Execution")
        layout.operator("greenscreen.render_clip", icon='RENDER_ANIMATION')

def register():
    bpy.utils.register_class(GREENSCREEN_OT_setup)
    bpy.utils.register_class(GREENSCREEN_OT_setup_passes)
    bpy.utils.register_class(GREENSCREEN_OT_render_clip)
    bpy.utils.register_class(GREENSCREEN_PT_panel)

def unregister():
    bpy.utils.unregister_class(GREENSCREEN_OT_setup)
    bpy.utils.unregister_class(GREENSCREEN_OT_setup_passes)
    bpy.utils.unregister_class(GREENSCREEN_OT_render_clip)
    bpy.utils.unregister_class(GREENSCREEN_PT_panel)

if __name__ == "__main__":
    register()
