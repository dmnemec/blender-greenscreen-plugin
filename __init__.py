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

        # 4. Set Color Management to Standard
        # This ensures that the green background is rendered as pure (0, 1, 0)
        scene.display_settings.display_device = 'sRGB'
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
        scene.view_settings.exposure = 0.0
        scene.view_settings.gamma = 1.0

        # 5. Set Output Format to OpenEXR RGBA
        scene.render.image_settings.file_format = 'OPEN_EXR'  # Use OpenEXR for high-bit depth output
        scene.render.image_settings.color_mode = 'RGBA' # Ensure alpha channel is included
        scene.render.image_settings.color_depth = '32' # Use 32-bit for maximum precision in AI data prep
        scene.render.image_settings.quality = 90 # DWAB compression quality
        scene.render.image_settings.exr_codec = 'DWAB'

        # 6. Setup World Background (Pure Green Screen)
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

        # 7. Disable Film Transparency to ensure the green background renders
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

        # 5. Setup Individual File Output Nodes for each directory
        # This ensures the OS-level folder structure is respected in 5.0.1
        passes = [
            ("Input", rl_input.outputs['Image'], (600, 400)),
            ("FG", rl_fg.outputs['Image'], (600, 150)),
            ("BG", rl_bg.outputs['Image'], (600, -100)),
            ("Alpha", rl_input.outputs['Alpha'], (600, -350))
        ]

        for pass_name, output_socket, loc in passes:
            # Create sub-directory physically
            os.makedirs(os.path.join(clip_path, pass_name), exist_ok=True)
            
            # Create and configure node
            node = nodes.new('CompositorNodeOutputFile')
            node.name = f"Output_{pass_name}"
            node.label = f"Export {pass_name}"
            node.location = loc
            
            # Blender 5.0 API: directory is the folder, file_name is the prefix
            node.directory = f"//{clip_name}/{pass_name}/"
            node.file_name = "render_"
            
            # Set format to OPEN_EXR_MULTILAYER as per your environment's valid list
            node.format.file_format = 'OPEN_EXR_MULTILAYER'
            node.format.exr_codec = 'DWAB'
            node.format.color_depth = '32'
            node.format.color_mode = 'RGBA'
            
            # In 5.0, the first item is created by default. 
            # We update its name to match the pass for clarity in the UI.
            if node.file_output_items:
                node.file_output_items[0].name = pass_name
            
            links.new(output_socket, node.inputs[0])

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
