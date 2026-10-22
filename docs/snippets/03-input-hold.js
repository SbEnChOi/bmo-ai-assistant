    const strong=this.level>=threshold;
    const sustaining=this.active&&this.level>=Math.max(threshold*.25,this.noise*1.6);
    if(strong){this.attack+=count;}
    else this.attack=0;
    if(strong||sustaining)this.nearMs+=count/this.rate*1000;
    else if(this.hold<=0)this.nearMs=0;
