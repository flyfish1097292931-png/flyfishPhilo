/* Entirely fictional. The sample records choices made by the fictional host. */
(function(root, make){ if(typeof module==='object' && module.exports) module.exports=make; else root.FlyfishPhiloDemo=make; })(globalThis, function(M){
  'use strict';
  let book=M.blank();
  function add(type,data){book=M.append(book,type,data);return book.events.at(-1).id;}
  const q=add('question',{text:'我不喜欢讨论，还是不喜欢被点名？'});
  const note=(question,source,text)=>add('note',{question,origin:'synthetic',source,text});
  const first=note(q,'虚构｜周四，读书会开场','主持人从左边逐一点名。我把准备说的一句划掉，等散场才说给身边的人听。');
  const other=note(q,'虚构｜散场后的楼梯','同一个话题，我和两位读者在楼梯口说了很久。人数没有变成一个，我却没有急着走。');
  const seed=add('seed',{question:q,text:'好像不是怕说话。听见自己的名字时，留给我选择的那一刻就已经过去了。'});
  add('idea',{question:q,kind:'reading',text:'轮到我时，拒绝比说一句无关紧要的话更显眼。',scope:'我记得的这两幕',why:'换了发言顺序，我对同一话题的反应也变了。',rival:'或许是楼梯口的两个人更熟。',test:'在熟人中也用轮流点名，看看我还会不会划掉那句话。',notes:[first,other],previous:null,seed});
  const v1=add('idea',{question:q,kind:'practice',text:'我主持时不再点名，只等自愿举手。',scope:'我主持的小型读书会',why:'这能去掉当众拒绝的那一下。',rival:'不点名也可能让不知道怎样加入的人一直等。',test:'会不会有人有话却等不到一个入口？',notes:[first,other],previous:null,seed:null});
  add('challenge',{idea:v1,note:other,verdict:'limit',detail:'散场后开口说明我能自愿参与，但不能说明每个人都能。这只能是一次可撤回的尝试。'});
  add('adopt',{idea:v1,review:'没有新读者的材料；不把我自己的经验推广到别人。',reason:'我愿意先试一场，只改变我的主持方式。',consent:true});
  add('trial',{idea:v1,step:'开场取消轮流点名，改为举手。'});
  const counter=note(q,'虚构｜第一次试行后的便笺','一位新读者写道：我等了一晚上，怕举手插进熟人的话里。要是先问过我愿不愿意被邀请就好了。');
  add('challenge',{idea:v1,note:counter,verdict:'counter',detail:'取消点名保护了一些人，也让另一个人失去入口。“只等举手”不能照旧用。'});
  add('withdraw',{idea:v1,reason:'撤回「只等举手」；保留当时的判断、试行和便笺。',consent:true});
  const v2=add('idea',{question:q,kind:'practice',text:'开始前让每个人选择自愿举手或接受邀请；当场跳过不必说明。',scope:'我主持、且能提前问到参与者的小型读书会',why:'把进入讨论的方式与拒绝的代价分别处理。',rival:'若主持人掌握评价权，私下选也可能有压力。',test:'选择跳过的人是否仍被追问？不愿举手的人是否真的获得入口？',notes:[first,counter],previous:v1,seed:null});
  add('challenge',{idea:v2,note:counter,verdict:'limit',detail:'双方只是获得不同入口；我不能从一张便笺断定所有人都感到自由。'});
  add('adopt',{idea:v2,review:'不外推到考核场景；若跳过的人被追问，下次暂停。',reason:'这两种入口都在我作为主持人可改变的范围内。',consent:true});
  const q2=add('question',{text:'名义上可以拒绝，就有拒绝的自由吗？'});
  const ab=note(q2,'虚构｜只改一个条件的思想实验','甲桌与乙桌都写着「可跳过」。甲桌跳过后立刻换人；乙桌要求当众说明原因。纸面规则相同。');
  const c=add('idea',{question:q2,kind:'claim',text:'判断一个人能否拒绝，至少要区分书面许可和实际要支付的代价。',scope:'涉及公开邀请和拒绝的交往',why:'两张桌子的许可相同，拒绝所需的动作却不同。',rival:'即便代价很高，拒绝作为法律或逻辑选项仍然存在。',test:'如果有代价就算不自由，连普通礼貌也会被误判；需要再区分哪些代价会取消选择。',notes:[ab,counter],previous:null,seed:null});
  add('link',{from:v2,to:c,relation:'requires',why:'主持规则用到了「可说不」与「说不的代价」的区分；一场读书会不能证明普遍的自由理论。'});
  add('seed',{question:q2,text:'可不可以把自由理解成：拒绝不需要额外为自己辩护？先不回答。'});
  add('rest',{question:q2});
  return book;
});
