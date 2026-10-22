# 【模块中文说明】
# 局部水位区域与原生土簇包围盒的保守几何判定。
# bb 的顺序固定为 xmin、ymin、xmax、ymax，polygon 为二维坐标顶点序列。
# 用多边形逐边裁剪计算交叠面积；仅当整个包围盒明确被同一区域包含时分配局部水位。
# 包围盒跨区时直接拒绝猜测，因此复杂斜交区域可能需要进一步切分。
# 
# 用鞋带公式计算闭合多边形面积绝对值，自动把末点与首点相连；空顶点序列返回 0。
def area(points):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2 if points else 0

# 将多边形依次裁剪到矩形包围盒的左、右、下、上四侧，返回交叠面积。
# 跨边界线段用线性参数求交点，完全位于边界外时提前返回 0。
def intersection_area(poly,bb):
    pts=[list(p) for p in poly]
    # Sutherland–Hodgman 裁剪：每次只保留一侧半平面中的顶点及跨边交点。
    # axis 选择 x/y，sign 指示矩形内侧，四轮之后得到多边形与矩形的交集。
    for axis,edge,sign in [(0,bb[0],1),(0,bb[2],-1),(1,bb[1],1),(1,bb[3],-1)]:
        output=[]
        if not pts:return 0
        for a,b in zip(pts[-1:]+pts[:-1],pts):
            ai=(a[axis]-edge)*sign>=0;bi=(b[axis]-edge)*sign>=0
            if ai!=bi:
                t=(edge-a[axis])/(b[axis]-a[axis]);output.append([a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])])
            if bi:output.append(b)
        pts=output
    return area(pts)

# 根据包围盒与局部水分区的面积关系返回唯一水分区 ID，未命中返回 None。
# 部分相交或多区域同时命中均报错；容差按包围盒面积缩放，避免微小浮点误差误判。
def containing_region(bb,regions):
    total=(bb[2]-bb[0])*(bb[3]-bb[1]);tol=max(total,1)*1e-8;found=[]
    for r in regions:
        overlap=intersection_area(r['polygon'],bb)
        if overlap>tol:
            if overlap<total-tol:raise ValueError('切分土体包围盒跨局部水分区，需进一步明确分区/切分，拒绝猜测')
            found.append(r['id'])
    if len(found)>1:raise ValueError('局部水条件重叠')
    return found[0] if found else None
