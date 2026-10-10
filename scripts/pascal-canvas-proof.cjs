'use strict';
function hasVisibleCanvas(bounds){
 return Array.isArray(bounds)&&bounds.some(b=>b&&b.visible===true&&Number.isFinite(b.width)&&Number.isFinite(b.height)&&b.width>=160&&b.height>=120);
}
module.exports={hasVisibleCanvas};
