#include "scene_2d.hpp"
#include <algorithm>
#include <cstdio>
#include <vector>
int main() {
    lab::scene2d::Scene scene;
    std::vector<lab::scene2d::Draw> draws;
    lab::Work work;
    if(!scene.prepare({lab::Scene::Wire,0,0},draws,work))return 1;
    for(int ty=0;ty<lab::height;ty+=32)for(int tx=0;tx<lab::width;tx+=32) {
        std::vector<lab::scene2d::Draw> tile;
        for(const auto &d:draws) {
            const int xmin=std::max(0,std::min(d.x0,d.x1)),xmax=std::min(lab::width-1,std::max(d.x0,d.x1));
            const int ymin=std::max(0,std::min(d.y0,d.y1)),ymax=std::min(lab::height-1,std::max(d.y0,d.y1));
            if(xmin<=xmax && ymin<=ymax && xmin/32<=tx/32 && xmax/32>=tx/32 && ymin/32<=ty/32 && ymax/32>=ty/32)tile.push_back(d);
        }
        if(tile.empty())continue;
        std::printf("%d %d %zu\n",tx,ty,tile.size());
        for(const auto &d:tile)
            std::printf("%d %d %d %d %u %u %u %u 0 0\n",d.x0-tx,d.y0-ty,d.x1-tx,d.y1-ty,
                lab::scene2d::pack(d.color),d.color>>8,d.color&255,unsigned(d.kind));
        return 0;
    }
    return 2;
}
