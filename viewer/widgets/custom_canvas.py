from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

class CustomCanvas(FigureCanvas):
    def __init__(self, fig, parent):
        super().__init__(fig)
        self.parent_app = parent

    def wheelEvent(self, event):
        if self.parent_app.view_mode != 'plot': return
        if not self.underMouse(): return
        
        delta = event.angleDelta().y()
        if delta == 0: return
        zoom_in = delta > 0

        is_3d = getattr(self.parent_app.ax, 'name', '') == '3d'

        if is_3d:
            factor = 1.15 if zoom_in else 0.85
            old_zoom = self.parent_app.cam_zoom
            self.parent_app.cam_zoom = max(1.0, min(self.parent_app.cam_zoom * factor, 15.0))
            
            if self.parent_app.cam_zoom == 1.0:
                self.parent_app.center_x = self.parent_app.abs_center_x
                self.parent_app.center_y = self.parent_app.abs_center_y
            elif old_zoom != self.parent_app.cam_zoom:
                d_zoom = self.parent_app.cam_zoom / old_zoom
                if zoom_in and self.parent_app.is_hovering:
                    self.parent_app.center_x = self.parent_app.hover_x - (self.parent_app.hover_x - self.parent_app.center_x) / d_zoom
                    self.parent_app.center_y = self.parent_app.hover_y - (self.parent_app.hover_y - self.parent_app.center_y) / d_zoom
                else:
                    self.parent_app.center_x = self.parent_app.abs_center_x - (self.parent_app.abs_center_x - self.parent_app.center_x) / d_zoom
                    self.parent_app.center_y = self.parent_app.abs_center_y - (self.parent_app.abs_center_y - self.parent_app.center_y) / d_zoom
            
            self.parent_app.apply_3d_zoom()
            
        else:
            factor = 1.15 if zoom_in else 0.85
            old_zoom = self.parent_app.cam_zoom_2d
            self.parent_app.cam_zoom_2d = max(1.0, min(self.parent_app.cam_zoom_2d * factor, 50.0))
            
            if self.parent_app.cam_zoom_2d == 1.0:
                self.parent_app.center_x_2d = (self.parent_app.abs_xlim[0] + self.parent_app.abs_xlim[1]) / 2.0
                self.parent_app.center_y_2d = (self.parent_app.abs_ylim[0] + self.parent_app.abs_ylim[1]) / 2.0
            elif old_zoom != self.parent_app.cam_zoom_2d:
                d_zoom = self.parent_app.cam_zoom_2d / old_zoom
                ax = self.parent_app.ax
                inv = ax.transData.inverted()
                pos = getattr(event, 'position', lambda: event.pos())()
                x_mouse, y_mouse = inv.transform((pos.x(), self.height() - pos.y()))
                
                self.parent_app.center_x_2d = x_mouse - (x_mouse - self.parent_app.center_x_2d) / d_zoom
                self.parent_app.center_y_2d = y_mouse - (y_mouse - self.parent_app.center_y_2d) / d_zoom
            
            self.parent_app.apply_2d_zoom()


