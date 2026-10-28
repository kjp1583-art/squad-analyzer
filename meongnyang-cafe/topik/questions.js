/* 제1회 박상준 한국어능력시험 — 읽기 문제 모음
 * 모든 지문은 상준 씨가 직접 알려 준 사실만으로 만들었다. 사실이 아닌 내용은 넣지 않는다.
 * head   : 시험지 머리글(※ 다음 글을 읽고…)
 * passage: 문단 배열(문단마다 한 줄)
 * stem   : 물음 / opts: 보기 4개 / ans: 정답 번호(0~3)
 * why    : 해설(쉬운 한국어) / vi: 지문의 베트남어 번역(AI 번역이라 어색할 수 있음)
 * gloss  : [낱말, 베트남어 뜻] — '베트남어 도움말'을 켜면 지문의 낱말에 밑줄이 생긴다
 */
window.TOPIK_QUESTIONS = [
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 서른두 살로, 고향은 서울이다. 그는 시설을 관리하는 일에 종사하고 있는데, 퇴근 후에는 곧장 귀가하는 대신 헬스장에 들러 운동을 한 뒤에야 집으로 돌아간다. 집에 도착하면 게임을 즐기는 것이 그의 하루를 마무리하는 방식이다.'],
    stem: '윗글의 내용과 같은 것을 고르십시오.',
    opts: ['박상준 씨의 고향은 서울이 아니다.', '박상준 씨는 퇴근한 뒤 헬스장에 들렀다가 귀가한다.', '박상준 씨는 집에 도착하자마자 운동을 시작한다.', '박상준 씨는 시설을 관리하는 일을 그만두었다.'],
    ans: 1,
    why: '글에 "헬스장에 들러 운동을 한 뒤에야 집으로 돌아간다"고 나와 있어요. 운동은 집이 아니라 헬스장에서 하고, 집에서는 게임을 해요.',
    vi: 'Anh Park Sang-jun 32 tuổi, quê ở Seoul. Anh làm công việc quản lý cơ sở vật chất; sau giờ làm anh không về thẳng nhà mà ghé phòng gym tập luyện rồi mới về. Về đến nhà, chơi game là cách anh kết thúc một ngày.',
    gloss: [['고향', 'quê hương'], ['시설', 'cơ sở vật chất, thiết bị'], ['종사하고', 'làm việc trong lĩnh vực… (종사하다)'], ['곧장', 'thẳng, ngay lập tức'], ['귀가하는', 'về nhà (귀가하다)'], ['들러', 'ghé qua (들르다)'], ['마무리하는', 'kết thúc, hoàn tất (마무리하다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨가 연인에게 마음을 고백한 것은 10월 19일이었다. 그가 고백 장소로 선택한 곳은 서울의 낙산공원이다. 자신의 마음을 상대에게 ( ㉠ ) 쉽지 않았겠지만, 그는 용기를 내어 진심을 전했다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['감추기가', '잊어버리기가', '털어놓기가', '따져 보기가'],
    ans: 2,
    why: '마음을 고백하는 상황이므로, 속에 있는 생각을 솔직하게 말한다는 뜻의 "털어놓다"가 알맞아요.',
    vi: 'Ngày anh Sang-jun tỏ tình với người yêu là 19/10. Nơi anh chọn để tỏ tình là công viên Naksan ở Seoul. Việc thổ lộ tình cảm của mình với đối phương hẳn không dễ dàng, nhưng anh đã lấy hết dũng khí để nói lời thật lòng.',
    gloss: [['고백한', 'tỏ tình (고백하다)'], ['고백', 'lời tỏ tình'], ['선택한', 'đã chọn (선택하다)'], ['용기', 'dũng khí'], ['진심', 'tấm lòng thật']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨가 즐겨 먹는 음식으로는 계란후라이, 치킨, 삼겹살이 꼽힌다. 반면에 가지와 피클은 그가 ㉠꺼리는 음식이다.'],
    stem: '밑줄 친 ㉠과 바꾸어 쓸 수 있는 것을 고르십시오.',
    opts: ['매우 즐기는', '싫어해서 피하는', '가끔 찾아 먹는', '처음 먹어 보는'],
    ans: 1,
    why: '"반면에"는 앞 문장과 반대되는 내용을 이어 줘요. 앞에서 좋아하는 음식을 말했으니, ㉠은 싫어한다는 뜻이에요. "꺼리다"는 싫어서 피한다는 뜻이에요.',
    vi: 'Các món anh Sang-jun thích ăn gồm trứng ốp la, gà rán và thịt ba chỉ nướng. Ngược lại, cà tím và dưa chuột muối chua là những món anh ngại ăn.',
    gloss: [['즐겨', 'thường hay, ưa thích'], ['꼽힌다', 'được kể đến, được nêu ra'], ['반면에', 'ngược lại'], ['꺼리는', 'ngại, né tránh']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨의 취미는 크게 두 가지로 나뉜다. 하나는 온라인 게임인 \'리그 오브 레전드\'를 즐기는 것이고, 다른 하나는 인공지능의 도움을 받아 프로그램을 만드는 이른바 \'바이브 코딩\'이다. 전자가 이미 만들어진 게임을 즐기는 활동이라면, 후자는 새로운 것을 직접 만들어 내는 활동이라는 점에서 서로 구별된다.'],
    stem: '이 글의 중심 내용으로 가장 알맞은 것을 고르십시오.',
    opts: ['박상준 씨는 게임을 그만두고 프로그램을 만들기 시작했다.', '박상준 씨는 온라인 게임보다 운동을 더 좋아한다.', '박상준 씨는 인공지능이 게임을 대신해 주기를 바란다.', '박상준 씨의 취미는 게임을 즐기는 것과 바이브 코딩, 두 가지이다.'],
    ans: 3,
    why: '글의 첫 문장이 중심 문장이에요. 취미가 "두 가지"로 나뉘고, 그 두 가지가 게임(리그 오브 레전드)과 바이브 코딩이라고 설명하고 있어요.',
    vi: 'Sở thích của anh Sang-jun chia làm hai. Một là chơi game trực tuyến "League of Legends", hai là cái gọi là "vibe coding" – tạo ra chương trình với sự trợ giúp của AI. Điểm khác nhau là: cái trước là chơi một trò chơi đã có sẵn, còn cái sau là hoạt động tự tay tạo ra điều mới.',
    gloss: [['취미', 'sở thích'], ['나뉜다', 'được chia ra (나뉘다)'], ['인공지능', 'trí tuệ nhân tạo (AI)'], ['이른바', 'cái gọi là'], ['전자', 'cái trước (trong hai cái)'], ['후자', 'cái sau (trong hai cái)'], ['구별된다', 'được phân biệt']]
  },
  {
    part: '읽기',
    head: '※ 다음을 순서에 맞게 배열한 것을 고르십시오.',
    passage: [
      '(가) 박상준 씨에게는 손톱을 물어뜯는 버릇이 있다.',
      '(나) 그러나 이러한 버릇과는 달리 그는 어떤 상황에서도 감정에 휩쓸리지 않고 언제나 이성적으로 생각하려고 한다.',
      '(다) 사람은 누구나 한두 가지쯤 고치기 어려운 습관을 지니기 마련이다.',
      '(라) 이와 같은 모습은 그의 다양한 면모를 보여 준다.'
    ],
    stem: '순서에 맞게 배열한 것은 무엇입니까?',
    opts: ['(가)-(나)-(다)-(라)', '(다)-(가)-(나)-(라)', '(가)-(다)-(라)-(나)', '(나)-(가)-(라)-(다)'],
    ans: 1,
    why: '먼저 일반적인 이야기(다)로 시작해요. 그다음 상준 씨의 버릇(가)이 나오고, "그러나"로 시작하는 (나)가 그 버릇과 반대되는 모습을 말해요. 마지막으로 "이와 같은 모습"을 정리하는 (라)가 와요.',
    vi: '(다) Ai cũng có đôi ba thói quen khó bỏ. (가) Anh Sang-jun có thói quen cắn móng tay. (나) Nhưng trái với thói quen đó, trong bất kỳ tình huống nào anh cũng không để cảm xúc cuốn đi mà luôn cố suy nghĩ một cách lý trí. (라) Những hình ảnh như vậy cho thấy nhiều khía cạnh khác nhau của anh.',
    gloss: [['물어뜯는', 'cắn xé (물어뜯다)'], ['버릇', 'thói quen (thường là xấu)'], ['휩쓸리지', 'bị cuốn theo (휩쓸리다)'], ['이성적', 'có lý trí, hợp lý'], ['습관', 'thói quen'], ['지니기', 'mang, có (지니다)'], ['면모', 'diện mạo, khía cạnh']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨는 약속 시간에 자주 늦는 편이다. 그럴 때면 박상준 씨는 애창곡인 버즈의 \'남자를 몰라\'를 부르곤 하는데, 이 노래에는 \'매번 늦어도 이해할게\'라는 구절이 나온다. 이 구절을 들은 투이 씨는 웃으면서 그를 때린다.'],
    stem: '노래를 들은 투이 씨의 반응으로 알맞은 것을 고르십시오.',
    opts: ['화를 내며 자리를 떠난다.', '아무 말 없이 고개를 숙인다.', '노래를 따라 부르며 춤을 춘다.', '웃으면서 상준 씨를 때린다.'],
    ans: 3,
    why: '마지막 문장에 "웃으면서 그를 때린다"고 나와 있어요. 진짜 화가 난 것이 아니라 웃으면서 장난스럽게 때리는 거예요.',
    vi: '투이 hay đến muộn giờ hẹn. Những lúc như vậy, anh Sang-jun thường hát bài hát yêu thích của Buzz là "Namjareul molla" (남자를 몰라), trong đó có câu "dù lần nào cũng đến muộn anh vẫn thông cảm". Nghe câu đó, 투이 vừa cười vừa đánh anh.',
    gloss: [['약속', 'cuộc hẹn'], ['편이다', 'thuộc dạng, khá là…'], ['애창곡', 'bài hát yêu thích hay hát'], ['구절', 'câu, đoạn (trong bài hát, bài văn)'], ['때린다', 'đánh (때리다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨에게 \'오늘 뭐 먹지?\'라고 물으면 돌아오는 대답은 번번이 같다. 바로 \'국물이 먹고 싶다\'는 것이다. 이처럼 어떤 질문에 대한 대답이 미리 정해져 있다시피 한 경우, 사람들은 질문을 던지기도 전에 대답을 짐작하기 마련이다.'],
    stem: '윗글을 통해 알 수 있는 것을 고르십시오.',
    opts: ['투이 씨는 메뉴를 물으면 늘 국물이 먹고 싶다고 답한다.', '투이 씨는 국물이 있는 음식을 먹지 않는다.', '투이 씨는 메뉴를 정할 때 상준 씨의 의견을 묻지 않는다.', '투이 씨는 질문을 받으면 대답을 오래 고민한다.'],
    ans: 0,
    why: '"대답은 번번이 같다"는 말은 항상 같은 대답을 한다는 뜻이에요. 그 대답이 "국물이 먹고 싶다"예요.',
    vi: 'Khi hỏi 투이 "hôm nay ăn gì?", câu trả lời lần nào cũng giống nhau. Đó là "em muốn ăn đồ có nước (canh)". Khi câu trả lời cho một câu hỏi gần như đã được định sẵn như vậy, người ta thường đoán được câu trả lời ngay cả trước khi đặt câu hỏi.',
    gloss: [['번번이', 'lần nào cũng'], ['국물', 'nước canh, nước dùng'], ['정해져', 'được định sẵn (정해지다)'], ['-다시피', 'gần như, hầu như'], ['짐작하기', 'đoán, phỏng đoán (짐작하다)'], ['-기 마련이다', 'chắc chắn sẽ…, vốn dĩ là…']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨는 베트남 사람으로, 여러 과일 가운데에서도 망고를 특히 좋아한다. 이러한 취향에 착안하여 박상준 씨는 인공지능의 도움을 받아 \'망고게임\'을 직접 만들었다. 이 게임에는 리치, 람부탄, 용과 등 베트남에서 흔히 볼 수 있는 과일이 등장하며, 같은 과일끼리 합치다 보면 마지막에 망고가 완성된다.'],
    stem: '윗글의 내용과 다른 것을 고르십시오.',
    opts: ['투이 씨는 베트남 사람이다.', '박상준 씨가 망고게임을 만들었다.', '망고게임에는 베트남에서 흔한 과일이 나온다.', '투이 씨는 망고보다 두리안을 더 좋아한다.'],
    ans: 3,
    why: '"다른 것"을 찾는 문제예요. 글에서는 투이 씨가 망고를 "특히" 좋아한다고 했고, 두리안을 더 좋아한다는 말은 없어요.',
    vi: '투이 là người Việt Nam, trong các loại trái cây thì đặc biệt thích xoài. Dựa trên sở thích đó, anh Sang-jun đã nhờ AI hỗ trợ và tự tay làm "Trò chơi Xoài". Trong trò chơi có những loại trái cây thường thấy ở Việt Nam như vải, chôm chôm, thanh long…, và khi ghép các quả giống nhau lại thì cuối cùng quả xoài sẽ hoàn thành.',
    gloss: [['취향', 'sở thích, gu'], ['착안하여', 'dựa vào ý tưởng (착안하다)'], ['흔히', 'thường, phổ biến'], ['등장하며', 'xuất hiện (등장하다)'], ['합치다', 'gộp lại, ghép lại'], ['완성된다', 'được hoàn thành']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 고양이를 좋아하는 반면, 투이 씨는 강아지를 좋아한다. ( ㉠ ) 두 사람이 함께 즐기는 게임에는 푸들과 고양이가 나란히 등장한다. ( ㉡ ) 게임을 만든 사람이 두 사람의 취향을 모두 반영하려 했기 때문이다. ( ㉢ )'],
    stem: '다음 문장이 들어갈 곳으로 알맞은 것을 고르십시오.\n〈보기〉 이는 우연이 아니다.',
    opts: ['㉠ 앞', '㉠', '㉡', '㉢'],
    ans: 2,
    why: '"이는"은 앞의 내용을 가리켜요. "푸들과 고양이가 나란히 등장한다"는 문장 뒤(㉡)에 "이는 우연이 아니다"가 오고, 그 이유가 이어져요.',
    vi: 'Anh Sang-jun thích mèo, còn 투이 thích chó. Trong trò chơi hai người cùng chơi, chó poodle và mèo xuất hiện cạnh nhau. (Điều này không phải ngẫu nhiên.) Đó là vì người làm game muốn phản ánh sở thích của cả hai.',
    gloss: [['-는 반면', 'trong khi đó, ngược lại'], ['나란히', 'song song, cạnh nhau'], ['등장한다', 'xuất hiện'], ['반영하려', 'định phản ánh (반영하다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨는 박상준 씨가 음식을 먹는 모습이 카피바라 같다며 자주 ㉠놀린다. 카피바라는 남아메리카에 서식하는 설치류로, 느긋한 성격으로 알려져 있다. 그래서 박상준 씨는 게임 속에 당근을 먹고 있는 카피바라를 직접 등장시켰다.'],
    stem: '밑줄 친 ㉠의 뜻으로 가장 알맞은 것을 고르십시오.',
    opts: ['장난삼아 상대를 웃음거리로 삼는다.', '진지하게 상대를 칭찬한다.', '몰래 숨어서 상대를 지켜본다.', '큰 소리로 상대를 꾸짖는다.'],
    ans: 0,
    why: '"놀리다"는 장난으로 상대를 웃음거리로 만든다는 뜻이에요. 투이 씨는 칭찬이 아니라 웃기려고 장난으로 말하는 거예요.',
    vi: '투이 thường trêu rằng dáng anh Sang-jun ăn giống capybara. Capybara là loài gặm nhấm sống ở Nam Mỹ, nổi tiếng với tính cách thong thả. Vì vậy, anh Sang-jun đã tự tay đưa nhân vật capybara đang ăn cà rốt vào trong trò chơi.',
    gloss: [['놀린다', 'trêu chọc (놀리다)'], ['서식하는', 'sinh sống (서식하다)'], ['설치류', 'loài gặm nhấm'], ['느긋한', 'thong thả, thư thả'], ['등장시켰다', 'cho xuất hiện (등장시키다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨가 \'개구리 고기를 먹자\'고 제안하면 박상준 씨는 먹기 싫다고 답한다. 두 사람 사이에서 이 장면은 정해진 대화처럼 되풀이된다. 이러한 농담이 오가는 모습을 보면 두 사람이 서로 얼마나 가까운 사이인지 짐작할 수 있다.'],
    stem: '윗글에서 알 수 있는 두 사람의 관계로 가장 알맞은 것을 고르십시오.',
    opts: ['서로의 말에 한 번도 대답하지 않는 사이', '처음 만나 어색한 사이', '장난스러운 농담을 주고받을 만큼 가까운 사이', '의견이 달라 자주 다투는 사이'],
    ans: 2,
    why: '같은 농담이 되풀이된다는 것은 서로 편하게 장난을 칠 수 있다는 뜻이에요. 글의 마지막 문장도 "얼마나 가까운 사이인지 짐작할 수 있다"고 말하고 있어요.',
    vi: 'Khi 투이 đề nghị "mình ăn thịt ếch đi", anh Sang-jun trả lời là không muốn ăn. Cảnh này giữa hai người lặp đi lặp lại như một đoạn hội thoại cố định. Nhìn những câu đùa qua lại như vậy có thể đoán được hai người thân thiết với nhau đến mức nào.',
    gloss: [['제안하면', 'nếu đề nghị (제안하다)'], ['되풀이된다', 'được lặp đi lặp lại'], ['농담', 'lời đùa'], ['오가는', 'qua lại (오가다)'], ['짐작할', 'đoán (짐작하다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 카페에서 휴대전화나 노트북으로 가볍게 즐길 수 있는 게임을 연인과 함께하고 싶어 했다. 그래서 그는 인공지능과 대화를 주고받으며 게임을 직접 만들기로 했다. 이때 그가 활용한 방식이 이른바 \'바이브 코딩\'이다. 바이브 코딩이란 프로그램의 세부 문법을 일일이 입력하는 대신, 원하는 바를 말로 설명하여 인공지능이 코드를 작성하도록 하는 방식을 가리킨다.'],
    stem: '\'바이브 코딩\'에 대한 설명으로 알맞은 것을 고르십시오.',
    opts: ['원하는 것을 말로 설명하여 인공지능이 코드를 쓰게 하는 방식', '문법을 하나하나 직접 입력하여 프로그램을 만드는 방식', '다른 사람이 만든 게임을 그대로 내려받아 즐기는 방식', '카페에서 만난 사람들과 함께 프로그램을 만드는 방식'],
    ans: 0,
    why: '글의 마지막 문장에 정의가 나와 있어요. "세부 문법을 일일이 입력하는 대신" 말로 설명해서 인공지능이 코드를 쓰게 한다고 했어요. 그래서 ②는 반대 설명이에요.',
    vi: 'Anh Sang-jun muốn cùng người yêu chơi một trò chơi nhẹ nhàng bằng điện thoại hoặc laptop ở quán cà phê. Vì vậy anh quyết định vừa trò chuyện với AI vừa tự tay làm trò chơi. Cách anh dùng chính là cái gọi là "vibe coding". Vibe coding là cách mà thay vì gõ từng chi tiết cú pháp của chương trình, ta mô tả bằng lời điều mình muốn để AI viết mã.',
    gloss: [['가볍게', 'một cách nhẹ nhàng'], ['활용한', 'đã tận dụng (활용하다)'], ['이른바', 'cái gọi là'], ['세부', 'chi tiết'], ['일일이', 'từng cái một'], ['작성하도록', 'để viết ra (작성하다)'], ['가리킨다', 'chỉ ra, có nghĩa là (가리키다)']]
  },

  /* ---- 어휘·문법 영역: 외국인이 헷갈리는 낱말과 문법 (13~28) ---- */
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨가 박상준 씨에 관한 문제의 정답을 모두 ( ㉠ ) 6급을 받을 수 있을 것이다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['맞추면', '맞으면', '맞히면', '맞게'], ans: 2,
    why: '문제의 답을 틀리지 않게 골라내는 것은 "맞히다"예요. "맞추다"는 퍼즐을 맞추다, 시간을 맞추다처럼 서로 어긋나지 않게 하는 것이고, "맞다"는 "을/를" 없이 써요.',
    vi: 'Nếu 투이 trả lời đúng tất cả đáp án của các câu hỏi về anh Sang-jun thì cô ấy có thể đạt cấp 6.',
    viWhy: '맞히다 = trả lời đúng, đoán trúng (đáp án). 맞추다 = ghép cho khớp, chỉnh cho đúng (ghép hình, chỉnh giờ, so đáp án). 맞다 = đúng (không đi với 을/를).',
    gloss: [['정답', 'đáp án đúng'], ['6급', 'cấp 6 (cao nhất của TOPIK)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨가 좋아하는 계란후라이를 ( ㉠ ) 때에는 팬에 기름을 두르고 불을 약하게 하는 것이 좋다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['붙일', '붙힐', '부칠', '불일'], ans: 2,
    why: '계란이나 전을 기름에 익혀 만드는 것은 "부치다"예요. "붙이다"는 물건을 맞닿게 하는 것(우표를 붙이다)이에요. "붙히다"와 "불일"은 없는 말이에요.',
    vi: 'Khi rán (ốp) trứng mà anh Sang-jun thích, tốt nhất nên cho dầu vào chảo và để lửa nhỏ.',
    viWhy: '부치다 = rán, chiên mỏng (trứng, bánh xèo); còn có nghĩa "gửi" (편지를 부치다). 붙이다 = dán, gắn vào (dán tem).',
    gloss: [['두르고', 'quét/đổ dầu lên bề mặt (두르다)'], ['약하게', 'nhỏ (lửa), yếu']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨는 고양이를, 투이 씨는 강아지를 좋아하므로 두 사람의 취향은 서로 ( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['틀리다', '다르다', '틀렸다', '다르게'], ans: 1,
    why: '"다르다"는 같지 않다는 뜻이고 "틀리다"는 맞지 않다, 잘못되었다는 뜻이에요. 취향이 같지 않은 것이므로 "다르다"가 맞아요. "다르게"는 문장을 끝낼 수 없어요.',
    vi: 'Anh Sang-jun thích mèo còn 투이 thích chó, nên sở thích của hai người khác nhau.',
    viWhy: '다르다 = khác nhau. 틀리다 = sai. Muốn nói "khác" thì dùng 다르다 (người Việt hay nhầm với 틀리다).',
    gloss: [['취향', 'sở thích, gu']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨처럼 언제나 이성적으로 생각하려면 ( ㉠ ) 감정과 사실을 구분할 줄 알아야 한다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['반듯이', '반들반들', '반듯하게', '반드시'], ans: 3,
    why: '"반드시"는 틀림없이, 꼭이라는 뜻이에요. "반듯이"는 모양이 비뚤어지지 않고 바르게라는 뜻이라서(반듯이 눕다) 여기에는 맞지 않아요.',
    vi: 'Muốn lúc nào cũng suy nghĩ lý trí như anh Sang-jun thì nhất định phải biết phân biệt cảm xúc và sự thật.',
    viWhy: '반드시 = nhất định, chắc chắn. 반듯이 = thẳng thắn, ngay ngắn (반듯이 눕다 = nằm thẳng). Hai từ phát âm gần giống nhau!',
    gloss: [['이성적', 'có lý trí'], ['구분할', 'phân biệt (구분하다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨는 요즘 한국어 시험 공부가 ( ㉠ )이다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['한창', '한참', '한층', '한껏'], ans: 0,
    why: '"한창"은 어떤 일이 가장 활발하게 진행되는 때예요. "한참"은 시간이 꽤 오래 지나는 동안(한참 기다리다), "한층"은 더욱, "한껏"은 할 수 있는 만큼 힘껏이라는 뜻이에요.',
    vi: 'Dạo này 투이 đang ở giai đoạn học thi tiếng Hàn sôi nổi nhất.',
    viWhy: '한창 = đang lúc sôi nổi nhất. 한참 = một lúc lâu. 한층 = hơn nữa, thêm một bậc. 한껏 = hết mức có thể.',
    gloss: [['한국어', 'tiếng Hàn'], ['시험', 'kỳ thi']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글을 읽고 ㉠과 ㉡에 들어갈 말을 순서대로 고르십시오.',
    passage: ['박상준 씨는 감정에 휩쓸리는 태도는 ( ㉠ )하고, 이성적으로 생각하는 태도를 ( ㉡ )한다.'],
    stem: '㉠, ㉡에 들어갈 말로 알맞은 것을 고르십시오.',
    opts: ['㉠ 지향 / ㉡ 지양', '㉠ 지양 / ㉡ 지양', '㉠ 지양 / ㉡ 지향', '㉠ 지향 / ㉡ 지향'], ans: 2,
    why: '"지양"은 하지 않으려고 피하는 것이고, "지향"은 어떤 방향을 목표로 삼아 나아가는 것이에요. 피하는 것은 감정에 휩쓸리는 태도, 나아가려는 것은 이성적인 태도예요.',
    vi: 'Anh Sang-jun tránh thái độ bị cảm xúc cuốn đi, và hướng tới thái độ suy nghĩ lý trí.',
    viWhy: '지양 = tránh, từ bỏ. 지향 = hướng tới, nhắm tới. Hai từ phát âm rất giống nhau nên dễ nhầm.',
    gloss: [['휩쓸리는', 'bị cuốn theo (휩쓸리다)'], ['태도', 'thái độ']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글을 읽고 ㉠과 ㉡에 들어갈 말을 순서대로 고르십시오.',
    passage: ['한국어 시험을 준비하는 투이 씨에게 어려운 문법을 ( ㉠ ) 주는 사람은 선생님이고, 손가락으로 방향을 ( ㉡ ) 사람은 안내원이다.'],
    stem: '㉠, ㉡에 들어갈 말로 알맞은 것을 고르십시오.',
    opts: ['㉠ 가르쳐 / ㉡ 가리키는', '㉠ 가리켜 / ㉡ 가르치는', '㉠ 가르쳐 / ㉡ 가르치는', '㉠ 가리켜 / ㉡ 가리키는'], ans: 0,
    why: '"가르치다"는 지식이나 기술을 알려 주는 것이고, "가리키다"는 손가락 등으로 방향이나 대상을 짚어 알리는 것이에요.',
    vi: 'Người dạy ngữ pháp khó cho 투이 đang chuẩn bị thi tiếng Hàn là giáo viên, còn người chỉ tay hướng dẫn phương hướng là nhân viên hướng dẫn.',
    viWhy: '가르치다 = dạy (kiến thức, kỹ năng). 가리키다 = chỉ (bằng ngón tay), chỉ ra. Hai từ phát âm gần giống nhau.',
    gloss: [['문법', 'ngữ pháp'], ['안내원', 'nhân viên hướng dẫn']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글을 읽고 ㉠과 ㉡에 들어갈 말을 순서대로 고르십시오.',
    passage: ['박상준 씨는 시설관리 일을 하는 직장인( ㉠ ) 퇴근 후에 운동을 하고, 인공지능에게 원하는 바를 말로 설명함( ㉡ ) 게임을 만들었다.'],
    stem: '㉠, ㉡에 들어갈 말로 알맞은 것을 고르십시오.',
    opts: ['㉠ 으로써 / ㉡ 으로써', '㉠ 으로써 / ㉡ 으로서', '㉠ 으로서 / ㉡ 으로서', '㉠ 으로서 / ㉡ 으로써'], ans: 3,
    why: '"(으)로서"는 신분이나 자격을 나타내요(직장인으로서). "(으)로써"는 방법이나 도구를 나타내요(말로 설명함으로써).',
    vi: 'Với tư cách là nhân viên làm công việc quản lý cơ sở vật chất, anh Sang-jun tập luyện sau giờ làm, và bằng cách mô tả điều mình muốn bằng lời cho AI, anh đã làm ra trò chơi.',
    viWhy: '(으)로서 = với tư cách là (chức vụ, vị trí). (으)로써 = bằng cách, bằng phương tiện.',
    gloss: [['직장인', 'người đi làm'], ['설명함', 'việc giải thích (설명하다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글을 읽고 ㉠과 ㉡에 들어갈 말을 순서대로 고르십시오.',
    passage: ['투이 씨가 망고를 좋아하는 것은 개인의 ( ㉠ )에 해당하고, 상준 씨가 리그 오브 레전드를 즐기는 것은 ( ㉡ )에 해당한다.'],
    stem: '㉠, ㉡에 들어갈 말로 알맞은 것을 고르십시오.',
    opts: ['㉠ 취미 / ㉡ 취향', '㉠ 취향 / ㉡ 취미', '㉠ 취향 / ㉡ 취향', '㉠ 취미 / ㉡ 취미'], ans: 1,
    why: '"취향"은 무엇을 좋아하는 마음의 방향이에요(좋아하는 과일, 색깔). "취미"는 여가 시간에 즐기는 활동이에요(게임, 운동).',
    vi: 'Việc 투이 thích xoài thuộc về gu (sở thích) cá nhân, còn việc anh Sang-jun chơi League of Legends thuộc về thú vui (hoạt động giải trí).',
    viWhy: '취향 = gu, điều mình thích (món ăn, màu sắc). 취미 = thú vui, hoạt động lúc rảnh. Cả hai đều hay dịch là "sở thích" nên dễ nhầm.',
    gloss: [['개인', 'cá nhân'], ['해당하고', 'thuộc về, tương ứng (해당하다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨는 시설을 관리하는 일을 ( ㉠ ) 퇴근 후에는 헬스장에서 운동까지 한다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['하는 바람에', '할 뿐만 아니라', '하는 탓에', '하더라도'], ans: 1,
    why: '앞 내용에 다른 내용을 더할 때는 "-(으)ㄹ 뿐만 아니라"를 써요. "-는 바람에"와 "-는 탓에"는 좋지 않은 결과의 이유를 말할 때 써요.',
    vi: 'Anh Sang-jun không chỉ làm công việc quản lý cơ sở vật chất mà sau giờ làm còn tập gym nữa.',
    viWhy: '-(으)ㄹ 뿐만 아니라 = không chỉ ... mà còn. -는 바람에 / -는 탓에 = vì ... nên (dẫn đến kết quả xấu). -더라도 = dù cho.',
    gloss: [['관리하는', 'quản lý (관리하다)'], ['헬스장', 'phòng gym']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['자주 늦는 투이 씨에게 화를 낼 ( ㉠ ) 하지만, 상준 씨는 노래로 마음을 전한다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['뻔도', '리도', '법도', '줄도'], ans: 2,
    why: '"-(으)ㄹ 법하다"는 그렇게 하는 것이 당연하다고 생각될 때 써요. "-(으)ㄹ 뻔하다"는 거의 그렇게 될 뻔했지만 되지 않았다는 뜻이에요.',
    vi: 'Với 투이 hay đến muộn thì cũng có lý khi anh nổi giận, nhưng anh Sang-jun lại gửi gắm tấm lòng bằng bài hát.',
    viWhy: '-(으)ㄹ 법하다 = cũng dễ hiểu nếu..., cũng có lý khi... -(으)ㄹ 뻔하다 = suýt nữa thì (nhưng đã không xảy ra).',
    gloss: [['전한다', 'truyền đạt (전하다)'], ['자주', 'thường xuyên']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨처럼 손톱을 자주 물어뜯으면 손톱 주변에 염증이 ( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['생기는 법이 없다', '생길 리가 없다', '생기기는커녕 없다', '생기기 십상이다'], ans: 3,
    why: '"-기 십상이다"는 그렇게 되기 쉽다는 뜻이에요(보통 좋지 않은 일). "-(으)ㄹ 리가 없다"는 그럴 가능성이 없다는 뜻이고, "-는 법이 없다"는 한 번도 그런 적이 없다는 뜻이에요.',
    vi: 'Nếu hay cắn móng tay như anh Sang-jun thì rất dễ bị viêm quanh móng.',
    viWhy: '-기 십상이다 = rất dễ (xảy ra điều không tốt). -(으)ㄹ 리가 없다 = không đời nào. -는 법이 없다 = chưa bao giờ.',
    gloss: [['물어뜯으면', 'nếu cắn xé (물어뜯다)'], ['염증', 'viêm, nhiễm trùng']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨가 \'개구리 고기를 먹자\'고 하면 상준 씨는 싫다고 답한다. 이처럼 상대방에게 억지로 음식을 ( ㉠ ) 것은 좋지 않다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['먹는', '먹히는', '먹이는', '먹어지는'], ans: 2,
    why: '"먹이다"는 "먹다"의 사동 표현으로, 다른 사람이 먹게 한다는 뜻이에요. "먹히다"는 피동 표현(먹음을 당하다)이에요.',
    vi: 'Khi 투이 nói "mình ăn thịt ếch đi", anh Sang-jun từ chối. Như vậy, ép người khác ăn là điều không tốt.',
    viWhy: '먹이다 = cho ăn, bắt ăn (thể sai khiến). 먹히다 = bị ăn (thể bị động).',
    gloss: [['억지로', 'một cách ép buộc'], ['상대방', 'đối phương']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['헬스장에서 운동하는 시간을 ( ㉠ ) 체력이 좋아진다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['늘이면', '늘리면', '늘어나면', '늘이도록'], ans: 1,
    why: '"늘리다"는 수나 양, 시간을 더 많게 한다는 뜻이고, "늘이다"는 길이를 더 길게 한다는 뜻이에요(고무줄을 늘이다). "늘어나다"는 스스로 많아진다는 뜻이라서 "시간을" 뒤에 쓸 수 없어요.',
    vi: 'Nếu tăng thời gian tập ở phòng gym thì thể lực sẽ tốt lên.',
    viWhy: '늘리다 = làm tăng (số lượng, thời gian). 늘이다 = làm dài ra (chiều dài). 늘어나다 = tự tăng lên (không có tân ngữ).',
    gloss: [['체력', 'thể lực']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨가 약속 시간에 늦었을 때 상준 씨가 ( ㉠ ) 반응했는지 궁금하다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['어떡해', '어떻게', '어떡게', '어떻해'], ans: 1,
    why: '"어떻게"는 방법이나 모양을 물을 때 쓰고 뒤에 동사나 형용사가 와요. "어떡해"는 "어떻게 해"의 줄임말로 문장을 끝낼 때 써요(어떡해!). "어떡게", "어떻해"는 틀린 표기예요.',
    vi: 'Tôi tò mò anh Sang-jun đã phản ứng như thế nào khi 투이 đến muộn giờ hẹn.',
    viWhy: '어떻게 = như thế nào (đứng trước động từ). 어떡해 = "làm sao bây giờ" (đứng cuối câu). 어떡게 và 어떻해 là viết sai.',
    gloss: [['반응했는지', 'đã phản ứng hay không (반응하다)'], ['궁금하다', 'tò mò']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['이성적으로 판단하려면 감정에 휩쓸리지 ( ㉠ ) 한다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['안아야', '않아야', '않어야', '안어야'], ans: 1,
    why: '"안"은 동사 앞에 쓰는 부정 부사(안 먹다)이고, "-지 않다"는 동사 뒤에 "-지"를 붙여 써요. "-지" 뒤에는 "않다"가 와요. "않아야"가 맞고 "않어야"는 틀려요.',
    vi: 'Muốn phán đoán một cách lý trí thì không được để cảm xúc cuốn đi.',
    viWhy: '안 + động từ (안 먹다) hoặc động từ + -지 않다 (먹지 않다). Sau -지 phải dùng 않다; chia là 않아야 (không phải 않어야).',
    gloss: [['판단하려면', 'nếu muốn phán đoán (판단하다)'], ['휩쓸리지', 'bị cuốn theo (휩쓸리다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 연인인 투이 씨를 \'자기\'라고 부른다. 그에게는 영문을 알 수 없는 일에 처했을 때 \'잉?\' 하고 되묻는 말버릇이 있다. 이처럼 말버릇은 무의식중에 튀어나오기 마련이어서, 본인조차 알아차리지 못하는 경우가 적지 않다.'],
    stem: '윗글의 내용과 같은 것을 고르십시오.',
    opts: ['박상준 씨는 화가 나면 \'잉?\' 하고 소리를 지른다.', '박상준 씨는 자신의 말버릇을 항상 의식하며 말한다.', '박상준 씨는 투이 씨의 말버릇을 따라 하고 있다.', '박상준 씨는 투이 씨를 \'자기\'라고 부른다.'], ans: 3,
    why: '첫 문장에 "투이 씨를 \'자기\'라고 부른다"고 나와 있어요. "잉?"은 화가 날 때가 아니라 영문을 알 수 없는 일에 처했을 때 하는 말이에요.',
    vi: 'Anh Sang-jun gọi người yêu 투이 là "자기" (cưng/em yêu). Anh có thói quen nói "잉?" để hỏi lại mỗi khi gặp chuyện không hiểu đầu đuôi. Thói quen nói như vậy thường bật ra vô thức nên không ít trường hợp chính người đó cũng không nhận ra.',
    gloss: [['영문', 'nguyên do, đầu đuôi (영문을 모르다 = không hiểu đầu đuôi)'], ['처했을', 'rơi vào tình huống (처하다)'], ['되묻는', 'hỏi lại (되묻다)'], ['말버릇', 'thói quen khi nói'], ['무의식중에', 'trong vô thức'], ['본인조차', 'ngay cả bản thân']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨의 리그 오브 레전드 포지션은 서포터이다. 서포터는 동료가 성장할 수 있도록 뒤에서 돕는 역할을 맡는다. 그가 즐겨 고르는 챔피언은 파이크이고, 그의 티어는 상위 등급에 속하는 마스터이다.'],
    stem: '윗글의 내용과 같은 것을 고르십시오.',
    opts: ['서포터는 앞에서 적을 공격하는 역할이다.', '박상준 씨의 티어는 마스터이다.', '박상준 씨는 포지션을 자주 바꾸는 편이다.', '박상준 씨가 즐겨 고르는 챔피언은 서포터이다.'], ans: 1,
    why: '"그의 티어는 ... 마스터이다"라고 나와 있어요. 서포터는 앞이 아니라 "뒤에서 돕는" 역할이고, 파이크는 챔피언의 이름이에요(서포터는 포지션).',
    vi: 'Vị trí chơi League of Legends của anh Sang-jun là Support (hỗ trợ). Support đảm nhận vai trò hỗ trợ từ phía sau để đồng đội có thể phát triển. Tướng anh hay chọn là Pyke, và bậc xếp hạng của anh là Cao Thủ (Master), thuộc nhóm cấp cao.',
    gloss: [['포지션', 'vị trí'], ['성장할', 'phát triển (성장하다)'], ['역할', 'vai trò'], ['챔피언', 'tướng (champion)'], ['티어', 'bậc xếp hạng (tier)'], ['속하는', 'thuộc về (속하다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 사계절 가운데 가을을 좋아하는 반면, 비가 오는 궂은 날씨는 싫어한다. 영화는 그다지 좋아하지 않으며, 카페에서는 아이스 카페라떼를 즐겨 주문한다. 그가 좋아하는 음식점으로는 BBQ가 있다.'],
    stem: '윗글의 내용과 다른 것을 고르십시오.',
    opts: ['박상준 씨는 가을을 좋아한다.', '박상준 씨는 비가 오는 날씨를 싫어한다.', '박상준 씨는 카페에서 아이스 카페라떼를 즐겨 주문한다.', '박상준 씨는 영화를 매우 좋아한다.'], ans: 3,
    why: '"다른 것"을 찾는 문제예요. 글에서는 영화를 "그다지 좋아하지 않는다"고 했는데, ④는 "매우 좋아한다"고 했으니 달라요.',
    vi: 'Anh Sang-jun thích mùa thu trong bốn mùa, nhưng ghét thời tiết xấu có mưa. Anh không thích phim ảnh cho lắm, ở quán cà phê anh hay gọi cà phê latte đá. Quán ăn anh thích là BBQ.',
    gloss: [['사계절', 'bốn mùa'], ['궂은', 'xấu (thời tiết) (궂다)'], ['그다지', '(không) ... lắm'], ['즐겨', 'thường hay, ưa'], ['음식점', 'quán ăn']]
  },
  {
    part: '읽기',
    head: '※ 다음을 순서에 맞게 배열한 것을 고르십시오.',
    passage: ['(가) 서포터는 동료를 뒤에서 돕는 역할이다.', '(나) 박상준 씨가 맡은 포지션이 바로 서포터이다.', '(다) 리그 오브 레전드에는 여러 가지 포지션이 있다.', '(라) 그가 즐겨 고르는 챔피언은 파이크이다.'],
    stem: '순서에 맞게 배열한 것은 무엇입니까?',
    opts: ['(가)-(나)-(다)-(라)', '(다)-(가)-(나)-(라)', '(다)-(나)-(가)-(라)', '(나)-(다)-(가)-(라)'], ans: 1,
    why: '먼저 큰 이야기(다: 여러 포지션)로 시작해요. 그다음 서포터가 어떤 역할인지(가)를 설명하고, 상준 씨의 포지션(나)과 그가 고르는 챔피언(라)이 이어져요.',
    vi: '(다) Trong League of Legends có nhiều vị trí khác nhau. (가) Support là vai trò hỗ trợ đồng đội từ phía sau. (나) Vị trí anh Sang-jun đảm nhận chính là Support. (라) Tướng anh hay chọn là Pyke.',
    viWhy: 'Sắp xếp từ chung đến riêng: nhiều vị trí → Support là gì → vị trí của anh ấy → tướng anh ấy chọn.',
    gloss: [['포지션', 'vị trí'], ['역할', 'vai trò'], ['맡은', 'đã đảm nhận (맡다)']]
  },
  {
    part: '읽기',
    head: '※ 다음 글을 읽고 이 글의 제목으로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨는 카페에서 연인과 함께 가볍게 즐길 수 있는 게임을 만들고 싶어 했다. 그래서 휴대전화와 노트북 어느 쪽에서든 접속할 수 있는 게임을 인공지능의 도움으로 만들었다. 이 게임에는 연인이 좋아하는 망고가 주인공으로 등장하는 게임도 포함되어 있다.'],
    stem: '이 글의 제목으로 가장 알맞은 것을 고르십시오.',
    opts: ['카페에서 팔고 있는 다양한 망고 음료', '상준 씨가 연인을 위해 직접 만든 게임', '인공지능이 대신 풀어 주는 어려운 시험 문제', '휴대전화와 노트북의 가격을 비교하는 방법'], ans: 1,
    why: '글 전체의 내용은 상준 씨가 연인과 함께 즐기려고 게임을 직접 만들었다는 것이에요. 다른 보기는 글에 나오지 않는 내용이에요.',
    vi: 'Anh Sang-jun muốn làm một trò chơi để cùng người yêu chơi nhẹ nhàng ở quán cà phê. Vì vậy anh đã nhờ AI giúp làm ra trò chơi có thể truy cập từ cả điện thoại và laptop. Trong đó có cả trò chơi lấy quả xoài mà người yêu thích làm nhân vật chính.',
    viWhy: 'Tiêu đề = nội dung chính của cả bài. Các lựa chọn khác không xuất hiện trong bài.',
    gloss: [['접속할', 'truy cập (접속하다)'], ['주인공', 'nhân vật chính'], ['포함되어', 'được bao gồm (포함되다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['박상준 씨는 영화 자체를 ( ㉠ ) 좋아하지 않는다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['매우', '아주', '그다지', '꽤'], ans: 2,
    why: '"그다지"는 뒤에 "않다, 없다" 같은 부정 표현이 올 때 써요(그다지 좋아하지 않는다). "매우, 아주, 꽤"는 긍정적인 정도를 나타내서 "좋아하지 않는다"와 어울리지 않아요.',
    vi: 'Anh Sang-jun không thích bản thân việc xem phim cho lắm.',
    viWhy: '그다지 / 별로 / 전혀 / 도무지 + phủ định = (không) ... lắm. 매우, 아주, 꽤 = rất, khá (dùng với khẳng định).',
    gloss: [['자체', 'bản thân (việc đó)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 밑줄 친 부분과 바꾸어 쓸 수 있는 것을 고르십시오.',
    passage: ['박상준 씨는 가을을 좋아하는 반면, 비가 오는 ㉠궂은 날씨는 싫어한다.'],
    stem: '밑줄 친 ㉠의 뜻으로 가장 알맞은 것을 고르십시오.',
    opts: ['비나 눈이 와서 좋지 않은', '맑고 화창한', '바람이 전혀 불지 않는', '매우 무더운'], ans: 0,
    why: '"궂다"는 날씨가 나쁘다는 뜻이에요. 비나 눈이 와서 좋지 않은 날씨를 "궂은 날씨"라고 해요.',
    vi: 'Anh Sang-jun thích mùa thu, nhưng ghét thời tiết xấu có mưa.',
    viWhy: '궂은 날씨 = thời tiết xấu (mưa, tuyết). Đối lập: 화창한 날씨 = thời tiết đẹp, nắng ấm.',
    gloss: [['가을', 'mùa thu'], ['반면', 'ngược lại']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 밑줄 친 부분과 바꾸어 쓸 수 있는 것을 고르십시오.',
    passage: ['박상준 씨는 영문을 알 수 없는 일에 ㉠처하면 \'잉?\' 하고 되묻는 말버릇이 있다.'],
    stem: '밑줄 친 ㉠과 바꾸어 쓸 수 있는 것을 고르십시오.',
    opts: ['멈추면', '벗어나면', '바라보면', '놓이면'], ans: 3,
    why: '"처하다"는 어떤 상황이나 처지에 놓이다라는 뜻이에요. 반대에 가까운 말은 "벗어나다"예요.',
    vi: 'Anh Sang-jun có thói quen nói "잉?" hỏi lại mỗi khi rơi vào chuyện không hiểu đầu đuôi.',
    viWhy: '처하다 = rơi vào, đặt vào (tình huống, hoàn cảnh). 벗어나다 = thoát khỏi.',
    gloss: [['영문', 'nguyên do (영문을 모르다 = không hiểu đầu đuôi)'], ['되묻는', 'hỏi lại']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨에게 \'오늘 뭐 먹지?\'라고 물으면 늘 같은 대답이 돌아온다. 투이 씨는 \'국물이 먹고 싶다\'는 대답( ㉠ ) 하지 않는다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['만', '조차', '마저', '밖에'], ans: 3,
    why: '"밖에"는 뒤에 "않다, 없다" 같은 부정 표현과 함께 써서 "그것뿐이다"라는 뜻을 나타내요. "조차"는 "그것까지도"라는 뜻이라서 앞 문장과 어울리지 않아요.',
    vi: 'Khi hỏi 투이 "hôm nay ăn gì?", lần nào cũng nhận được cùng một câu trả lời. 투이 chỉ trả lời "em muốn ăn đồ có nước (canh)" mà thôi.',
    viWhy: '-밖에 + phủ định = chỉ có ... thôi. -조차 = ngay cả (điều không ngờ tới). -만 = chỉ. -마저 = đến cả (cái cuối cùng).',
    gloss: [['대답', 'câu trả lời'], ['돌아온다', 'được đáp lại (돌아오다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨는 상준 씨에게 "개구리 고기를 먹자."라고 말했다. 이 말을 간접 화법으로 바꾸면 "투이 씨는 상준 씨에게 개구리 고기를 ( ㉠ ) 말했다."가 된다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['먹냐고', '먹으라고', '먹자고', '먹는다고'], ans: 2,
    why: '"-자"로 제안하는 말은 간접 화법에서 "-자고"로 바꿔요. 질문은 "-냐고", 명령은 "-(으)라고", 설명은 "-ㄴ/는다고"로 바꿔요.',
    vi: 'Khi chuyển lời rủ "mình ăn thịt ếch đi" sang câu gián tiếp thì dùng -자고.',
    viWhy: 'Câu gián tiếp: rủ rê → -자고, nghi vấn → -냐고, mệnh lệnh → -(으)라고, trần thuật → -ㄴ/는다고.',
    gloss: [['간접 화법', 'câu gián tiếp'], ['바꾸면', 'nếu đổi (바꾸다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['리그 오브 레전드에서 서포터는 동료를 ( ㉠ ) 역할을 맡는다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['돕은', '도운', '도우는', '돕는'], ans: 3,
    why: '"돕다"는 ㅂ 불규칙 동사예요. 현재 관형형은 "돕는"이고, 과거는 "도운", 모음 앞에서는 "도와/도우면"처럼 바뀌어요.',
    vi: 'Trong LoL, Support đảm nhận vai trò giúp đỡ đồng đội.',
    viWhy: '돕다 là động từ bất quy tắc ㅂ: 돕는 (hiện tại, định ngữ), 도운 (quá khứ), 도와요, 도우면. Trước phụ âm giữ nguyên 돕-.',
    gloss: [['서포터', 'người hỗ trợ (Support)'], ['동료', 'đồng đội'], ['맡는다', 'đảm nhận (맡다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['손톱 주변의 염증이 ( ㉠ ) 때까지는 손톱을 물어뜯지 않는 것이 좋다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['날', '낳을', '낮을', '나을'], ans: 3,
    why: '병이나 상처가 없어지는 것은 "낫다"예요(ㅅ 불규칙: 나을, 나아). "낳다"는 아기를 낳다, "낮다"는 높지 않다는 뜻이에요.',
    vi: 'Nên tránh cắn móng tay cho đến khi chỗ viêm quanh móng khỏi hẳn.',
    viWhy: '낫다 = khỏi (bệnh), bất quy tắc ㅅ: 나을, 나아요. 낳다 = sinh, đẻ. 낮다 = thấp. Ba từ phát âm gần giống nhau.',
    gloss: [['염증', 'viêm, nhiễm trùng'], ['물어뜯지', 'cắn xé (물어뜯다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['투이 씨가 \'개구리 고기를 먹자\'고 하면, 개구리 고기가 싫은 상준 씨는 거절( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['할 리가 없다', '할 뻔했다', '할 만하다', '할 수밖에 없다'], ans: 3,
    why: '"-(으)ㄹ 수밖에 없다"는 다른 방법이 없어서 그렇게 할 수밖에 없다는 뜻이에요. "-(으)ㄹ 리가 없다"는 그럴 가능성이 없다는 뜻이에요.',
    vi: 'Khi 투이 rủ "ăn thịt ếch đi", anh Sang-jun vì không thích thịt ếch nên đành phải từ chối.',
    viWhy: '-(으)ㄹ 수밖에 없다 = đành phải, không còn cách nào khác. -(으)ㄹ 리가 없다 = không đời nào. -(으)ㄹ 뻔하다 = suýt nữa.',
    gloss: [['거절', 'sự từ chối']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['가지와 피클을 싫어하는 상준 씨가 가지 요리를 즐겨 먹을 ( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['법하다', '리가 없다', '뻔했다', '만하다'], ans: 1,
    why: '"-(으)ㄹ 리가 없다"는 그럴 가능성이 전혀 없다고 생각할 때 써요. 가지를 싫어하니까 즐겨 먹을 가능성이 없다는 뜻이에요.',
    vi: 'Anh Sang-jun ghét cà tím và dưa chuột muối thì không đời nào lại thích ăn món cà tím.',
    viWhy: '-(으)ㄹ 리가 없다 = không thể nào, không đời nào. Khác với -(으)ㄹ 법하다 (cũng có lý) và -(으)ㄹ 만하다 (đáng để).',
    gloss: [['요리', 'món ăn, nấu ăn']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['계란후라이는 만들기도 쉽고, 상준 씨가 좋아할 ( ㉠ ) 음식이다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['리가 없는', '뻔한', '탓인', '만한'], ans: 3,
    why: '"-(으)ㄹ 만하다"는 그럴 가치나 이유가 충분하다는 뜻이에요. "좋아할 만한 음식"은 좋아할 이유가 충분한 음식이라는 뜻이에요.',
    vi: 'Trứng ốp la vừa dễ làm, vừa là món anh Sang-jun có thể thích.',
    viWhy: '-(으)ㄹ 만하다 = đáng để, xứng đáng, có lý do để. 좋아할 만한 음식 = món đáng để thích.',
    gloss: [['음식', 'món ăn']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['비가 오면 상준 씨가 싫어할 ( ㉠ ) 우산을 챙기자.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['텐데', '뿐인데', '바람에', '대로'], ans: 0,
    why: '"-(으)ㄹ 텐데"는 추측하면서 뒤에 이어질 말의 이유나 배경을 말할 때 써요. "싫어할 텐데 우산을 챙기자"는 싫어할 것 같으니 준비하자는 뜻이에요.',
    vi: 'Nếu trời mưa thì chắc anh Sang-jun sẽ không thích, nên mình mang ô theo nhé.',
    viWhy: '-(으)ㄹ 텐데 = chắc là ... nên/mà... (suy đoán + lý do cho vế sau). -는 바람에 = vì ... (kết quả xấu đã xảy ra).',
    gloss: [['챙기자', 'mang theo, chuẩn bị (챙기다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨는 이성적으로 생각하는 사람이어서 감정이 시키는 ( ㉠ ) 행동하지 않는다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['만큼', '대로', '채로', '뿐'], ans: 1,
    why: '"-는 대로"는 앞의 내용과 똑같이라는 뜻이에요. "감정이 시키는 대로"는 감정이 시키는 그대로라는 뜻이에요.',
    vi: 'Vì là người suy nghĩ lý trí nên anh Sang-jun không hành động theo đúng những gì cảm xúc mách bảo.',
    viWhy: '-는 대로 = theo đúng như, y như. -(으)ㄴ 채로 = trong trạng thái nguyên như vậy. -(으)ㄴ 만큼 = bằng mức, vì ... nên.',
    gloss: [['시키는', 'sai khiến, bảo làm (시키다)'], ['행동하지', 'hành động (행동하다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨는 마스터 티어를 달성한 ( ㉠ ) 게임 실력이 뛰어나다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['탓에', '대신', '만큼', '채로'], ans: 2,
    why: '"-(으)ㄴ 만큼"은 앞 내용의 정도나 이유에 걸맞게라는 뜻이에요. 마스터 티어를 달성했으니 실력이 뛰어난 것이 당연하다는 뜻이에요.',
    vi: 'Vì đã đạt bậc Cao Thủ nên kỹ năng chơi game của anh Sang-jun rất giỏi.',
    viWhy: '-(으)ㄴ 만큼 = tương xứng với, vì ... nên (kết quả tương xứng). -는 탓에 = vì (lỗi) ... (kết quả xấu).',
    gloss: [['달성한', 'đạt được (달성하다)'], ['뛰어나다', 'xuất sắc, giỏi']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['낙산공원에 올라가면 서울 시내가 한눈에 ( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['본다', '보여 준다', '보게 한다', '보인다'], ans: 3,
    why: '"보이다"는 "보다"의 피동 표현으로, 저절로 눈에 들어온다는 뜻이에요. 서울 시내가(주어) 눈에 들어오는 것이므로 "보인다"가 알맞아요.',
    vi: 'Lên công viên Naksan là có thể nhìn thấy toàn cảnh nội thành Seoul chỉ trong một cái nhìn.',
    viWhy: '보이다 = nhìn thấy, hiện ra trước mắt (thể bị động của 보다). 보다 = nhìn (chủ động, cần tân ngữ).',
    gloss: [['시내', 'nội thành'], ['한눈에', 'trong một cái nhìn']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨가 투이 씨 앞에서 부르는 노래는 투이 씨를 ( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['웃었다', '웃혔다', '웃이었다', '웃겼다'], ans: 3,
    why: '"웃기다"는 "웃다"의 사동 표현으로, 다른 사람을 웃게 한다는 뜻이에요. "웃겼다"가 맞고 "웃혔다"는 없는 말이에요.',
    vi: 'Bài hát anh Sang-jun hát trước mặt 투이 đã làm 투이 bật cười.',
    viWhy: '웃다 = cười. 웃기다 = làm cho (ai) cười (thể sai khiến), quá khứ 웃겼다.',
    gloss: [['앞에서', 'trước mặt']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨는 이성적인 사람이라 ( ㉠ ) 감정에 휩쓸리지 않는다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['자주', '종종', '좀처럼', '가끔'], ans: 2,
    why: '"좀처럼"은 뒤에 부정 표현과 함께 써서 "쉽게는 ~하지 않는다"는 뜻을 나타내요. "자주, 종종, 가끔"은 부정 표현과 쓰면 어색해요.',
    vi: 'Anh Sang-jun là người lý trí nên hiếm khi bị cảm xúc cuốn đi.',
    viWhy: '좀처럼 + phủ định = hiếm khi, khó mà... (좀처럼 화내지 않는다 = khó mà nổi giận).',
    gloss: [['이성적인', 'có lý trí'], ['휩쓸리지', 'bị cuốn theo']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['가지와 피클을 싫어하는 상준 씨는 입이 ( ㉠ ) 편인가 보다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['작은', '짧은', '좁은', '적은'], ans: 1,
    why: '"입이 짧다"는 음식을 가려 먹고 입맛이 까다롭다는 뜻의 관용 표현이에요. "입이 작다", "입이 좁다"는 이런 뜻으로 쓰지 않아요.',
    vi: 'Ghét cà tím và dưa chuột muối, chắc anh Sang-jun thuộc dạng kén ăn.',
    viWhy: '입이 짧다 = kén ăn (thành ngữ). Không dùng 입이 작다/좁다 để nói kén ăn.',
    gloss: [['편인가', 'thuộc dạng (편이다)'], ['보다', 'có lẽ (-ㄴ가 보다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글을 읽고 밑줄 친 속담의 뜻으로 알맞은 것을 고르십시오.',
    passage: ['투이 씨가 \'개구리 고기를 먹자\'고 하자 상준 씨는 웃으며 거절했다. 한국에는 ㉠\'개구리 올챙이 적 생각 못 한다\'는 속담이 있다.'],
    stem: '밑줄 친 ㉠의 뜻으로 가장 알맞은 것을 고르십시오.',
    opts: ['형편이 나아진 뒤에 지난날의 어려움을 잊고 처음부터 잘난 줄 안다', '작은 일에도 크게 놀라는 사람을 놀린다', '다른 사람의 일에 쓸데없이 참견한다', '좋은 일은 반드시 나쁜 일로 끝난다'], ans: 0,
    why: '올챙이는 개구리의 어릴 때 모습이에요. 개구리가 자기가 올챙이였던 때를 잊는 것처럼, 형편이 나아지면 어려웠던 지난날을 잊는다는 뜻이에요.',
    vi: 'Khi 투이 rủ "ăn thịt ếch đi", anh Sang-jun cười và từ chối. Ở Hàn Quốc có câu tục ngữ "Ếch không nhớ thời còn là nòng nọc".',
    viWhy: '개구리 올챙이 적 생각 못 한다 = quên mất thời khó khăn của mình khi đã khá lên, tưởng mình vốn giỏi giang từ đầu.',
    gloss: [['올챙이', 'nòng nọc'], ['속담', 'tục ngữ'], ['거절했다', 'đã từ chối (거절하다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글을 읽고 밑줄 친 속담의 뜻으로 알맞은 것을 고르십시오.',
    passage: ['마스터 티어인 상준 씨도 가끔 게임에서 질 때가 있다. ㉠\'원숭이도 나무에서 떨어진다\'는 말은 이런 경우에 어울린다.'],
    stem: '밑줄 친 ㉠의 뜻으로 가장 알맞은 것을 고르십시오.',
    opts: ['원숭이는 나무를 오르는 것을 좋아한다', '아무리 잘하는 사람도 실수할 때가 있다', '나무에서 떨어지면 크게 다친다', '높은 곳에 올라가면 위험하다'], ans: 1,
    why: '나무타기를 잘하는 원숭이도 떨어질 때가 있듯이, 아무리 잘하는 사람도 실수할 수 있다는 뜻이에요. 이 뜻을 나타내는 대표적인 속담이에요.',
    vi: 'Anh Sang-jun dù ở bậc Cao Thủ thỉnh thoảng vẫn thua game. Câu "Khỉ cũng có lúc rơi khỏi cây" hợp với trường hợp này.',
    viWhy: '원숭이도 나무에서 떨어진다 = người giỏi mấy cũng có lúc sai sót (tương đương "nhân vô thập toàn").',
    gloss: [['어울린다', 'hợp với (어울리다)'], ['티어', 'bậc xếp hạng (tier)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨가 투이 씨에게 고백했( ㉠ ) 낙산공원에는 오늘도 많은 사람이 찾아왔다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['는', 'ㄴ', '을', '던'], ans: 3,
    why: '"-았/었던"은 과거에 있었던 일을 회상하며 말할 때 써요. "고백했던 낙산공원"은 고백한 일을 떠올리며 말하는 표현이에요. "고백했ㄴ"과 "고백했는"은 틀린 표현이에요.',
    vi: 'Công viên Naksan nơi anh Sang-jun đã từng tỏ tình với 투이 hôm nay cũng có rất nhiều người đến.',
    viWhy: '-았/었던 = (đã từng) ... mà ... (hồi tưởng chuyện quá khứ). 했는/했ㄴ là sai.',
    gloss: [['고백했', 'đã tỏ tình (고백하다)'], ['찾아왔다', 'đã tìm đến (찾아오다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨의 하루는 \'일, 헬스장, 집\' 순서로 흘러가니, 헬스장도 하루의 일과인 ( ㉠ ).'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['셈이다', '뻔이다', '법이다', '리이다'], ans: 0,
    why: '"-(으)ㄴ/는 셈이다"는 결과적으로 그렇다고 볼 수 있다는 뜻이에요. 하루의 순서에 헬스장이 들어 있으니 일과인 셈이에요.',
    vi: 'Ngày của anh Sang-jun trôi qua theo thứ tự "công việc, phòng gym, nhà", nên có thể coi phòng gym cũng là một phần lịch trình hằng ngày.',
    viWhy: '-(으)ㄴ/는 셈이다 = coi như là, xem như là (xét theo kết quả). Các lựa chọn còn lại không tạo thành câu đúng ở đây.',
    gloss: [['일과', 'lịch trình trong ngày'], ['흘러가니', 'trôi qua (흘러가다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨가 투이 씨( ㉠ ) 노래를 불러 준다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['에서', '보다', '에게', '처럼'], ans: 2,
    why: '"에게"는 행동을 받는 사람 뒤에 써요. 노래를 불러 주는 대상이 투이 씨이므로 "에게"가 알맞아요. "에서"는 장소, "보다"는 비교, "처럼"은 모양을 나타내요.',
    vi: 'Anh Sang-jun hát bài hát cho 투이 nghe.',
    viWhy: '에게 = cho, đối với (người nhận hành động). 에서 = ở (nơi chốn). 보다 = hơn (so sánh). 처럼 = giống như.',
    gloss: [['불러', 'hát (부르다)']]
  },
  {
    part: '어휘·문법',
    head: '※ 다음 글의 ( ㉠ )에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    passage: ['상준 씨가 즐겨 마시는 아이스 카페라떼는 얼음이 ( ㉠ ) 맛이 연해진다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['녹자마자', '녹느라고', '녹을수록', '녹는데도'], ans: 2,
    why: '"-(으)ㄹ수록"은 앞의 정도가 더해지는 것에 따라 뒤의 정도도 달라진다는 뜻이에요. 얼음이 녹는 정도가 더해질수록 맛이 연해져요.',
    vi: 'Cà phê latte đá mà anh Sang-jun hay uống càng để đá tan thì vị càng nhạt.',
    viWhy: '-(으)ㄹ수록 = càng ... càng ... -자마자 = vừa ... thì ngay. -느라고 = vì mải ... nên.',
    gloss: [['얼음', 'đá (nước đá)'], ['연해진다', 'trở nên nhạt (연해지다)']]
  }
];
