# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Shape Key Retarget Tool",
    "author" : "Kumopult",
    "description" : "使用表面形变（Surface Deform）修改器来批量重定向形态键",
    "blender" : (2, 93, 0),
    "version" : (0, 0, 1),
    "location" : "View 3D > Toolshelf",
    "warning" : "因为作者很懒所以没写英文教学！",
    "category" : "Generic"
    # VScode调试：Ctrl + Shift + P
}

import bpy
from bpy import context

class SKR_PT_Panel(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ShapeKeyRetarget"
    bl_label = "Shape Key Retarget Tool"

    def draw(self, context):
        layout = self.layout
        
        if context.object != None:
            s: SKR_State = bpy.context.scene.kumopult_skr

            split = layout.row().split(factor=0.25)
            split.column().label(text='重定向目标:')
            split.column().label(text=context.object.name, icon='OUTLINER_DATA_MESH')
            target_row = layout.row()
            target_row.prop(s, 'target', text='形态键来源', icon='OUTLINER_DATA_MESH')
            target_row.alert = s.target_valid()
            layout.template_list('SKR_UL_Keys', '', s, 'retargeted_keys', s, 'active_key')
            layout.operator(SKR_OT_Retarget.bl_idname, text='重定向形态键')
        else:
            layout.label(text='未选中对象', icon='ERROR')

class SKR_UL_Keys(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index, flt_flag):
        owner_keys = bpy.context.object.data.shape_keys
        if owner_keys and owner_keys.key_blocks.get(item.name):
            layout.prop(item, 'valid', text=item.name, icon="FILE_REFRESH", expand=True)
        else:
            layout.prop(item, 'valid', text=item.name, icon="SHAPEKEY_DATA", expand=True)

class SKR_Key(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    valid: bpy.props.BoolProperty(name="传递此形态键")

class SKR_State(bpy.types.PropertyGroup):
    owner = property(lambda self: bpy.context.object)
    target: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH' and obj.data.shape_keys,
        update=lambda self, ctx: self.update_target()
    )

    retargeted_keys: bpy.props.CollectionProperty(type=SKR_Key)
    active_key: bpy.props.IntProperty()

    def owner_valid(self):
        return self.target.type == 'MESH'

    def target_valid(self):
        return self.target.type == 'MESH' and self.target != self.owner and self.target.data.shape_keys != None

    def update_target(self):
        self.retargeted_keys.clear()
        blocks = self.target.data.shape_keys.key_blocks
        for i in range(1, len(blocks)):
            k = self.retargeted_keys.add()
            k.name = blocks[i].name
            k.valid = True

class SKR_OT_Retarget(bpy.types.Operator):
    bl_idname = 'kumopult_skr.retarget'
    bl_label = '形态键重定向'
    bl_description = ''

    @classmethod
    def poll(cls, context):
        s: SKR_State = context.scene.kumopult_skr
        return s.target_valid() and s.owner_valid()

    def execute(self, context):
        s: SKR_State = context.scene.kumopult_skr

        # 若已存在表面形变修改器，则直接获取，否则新建
        sd: bpy.types.SurfaceDeformModifier = None
        for modifier in s.owner.modifiers:
            if modifier.type == "SURFACE_DEFORM":
                sd = modifier
        sd_flag = False
        if not sd:
            sd = s.owner.modifiers.new(type="SURFACE_DEFORM", name="SurfaceDeform")
            sd.target = s.target
            bpy.ops.object.surfacedeform_bind(modifier="SurfaceDeform")
        else:
            # 已有手动添加的表面形变修改器的情况下，插件并不希望在重定向完成后删除辛苦绑好的修改器
            # 因此需要记录一下使用的修改器是脚本添加的还是手动添加的，如果是后者，则会在完成后将修改器效果关闭作为代替
            sd.show_viewport = True 
            sd_flag = True

        owner_blocks = None
        if s.owner.data.shape_keys:
            owner_blocks = s.owner.data.shape_keys.key_blocks
        target_blocks = s.target.data.shape_keys.key_blocks
        
        # 归零所有目标形态键
        for target_block in target_blocks:
            target_block.value = 0

        for k in s.retargeted_keys:
            if not k.valid:
                continue
            
            owner_index = -1
            if owner_blocks:
                owner_index = owner_blocks.find(k.name)
                if owner_index > 0:
                    s.owner.active_shape_key_index = owner_index
                    bpy.ops.object.shape_key_remove(all=False)

            target_block: bpy.types.ShapeKey = target_blocks.get(k.name)
            target_block.value = 1
            sd.name = k.name # 将修改器名称修改后，应用为修改器时生成的形态键就会是修改器的名字
            bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=True, modifier=k.name)
            target_block.value = 0

            if owner_index > 0:
                s.owner.active_shape_key_index = len(owner_blocks) - 1
                while s.owner.active_shape_key_index != owner_index:
                    bpy.ops.object.shape_key_move(type='UP')

        if sd_flag:
            sd.name = "SurfaceDeform" # 完事后把名字改回来
            sd.show_viewport = False
        else:
            s.owner.modifiers.remove(sd)

        return {'FINISHED'}

classes = (
	SKR_PT_Panel,
    SKR_UL_Keys,
    SKR_Key,
    SKR_State,
    SKR_OT_Retarget,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kumopult_skr = bpy.props.PointerProperty(type=SKR_State)
    print("hello kumopult!")

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.kumopult_skr
    print("goodbye kumopult!")
