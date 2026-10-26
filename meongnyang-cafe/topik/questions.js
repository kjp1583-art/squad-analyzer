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
    head: '※ [1~2] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 서른두 살로, 고향은 서울이다. 그는 시설을 관리하는 일에 종사하고 있는데, 퇴근 후에는 곧장 귀가하는 대신 헬스장에 들러 운동을 한 뒤에야 집으로 돌아간다. 집에 도착하면 게임을 즐기는 것이 그의 하루를 마무리하는 방식이다.'],
    stem: '윗글의 내용과 같은 것을 고르십시오.',
    opts: ['박상준 씨의 고향은 서울이 아니다.', '박상준 씨는 퇴근한 뒤 헬스장에 들렀다가 귀가한다.', '박상준 씨는 집에 도착하자마자 운동을 시작한다.', '박상준 씨는 시설을 관리하는 일을 그만두었다.'],
    ans: 1,
    why: '글에 "헬스장에 들러 운동을 한 뒤에야 집으로 돌아간다"고 나와 있어요. 운동은 집이 아니라 헬스장에서 하고, 집에서는 게임을 해요.',
    vi: 'Anh Park Sang-jun 32 tuổi, quê ở Seoul. Anh làm công việc quản lý cơ sở vật chất; sau giờ làm anh không về thẳng nhà mà ghé phòng gym tập luyện rồi mới về. Về đến nhà, chơi game là cách anh kết thúc một ngày.',
    gloss: [['고향', 'quê hương'], ['시설', 'cơ sở vật chất, thiết bị'], ['종사하고', 'làm việc trong lĩnh vực… (종사하다)'], ['곧장', 'thẳng, ngay lập tức'], ['귀가하는', 'về nhà (귀가하다)'], ['들러', 'ghé qua (들르다)'], ['마무리하는', 'kết thúc, hoàn tất (마무리하다)']]
  },
  {
    head: '※ [1~2] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨가 연인에게 마음을 고백한 것은 10월 19일이었다. 그가 고백 장소로 선택한 곳은 서울의 낙산공원이다. 자신의 마음을 상대에게 ( ㉠ ) 쉽지 않았겠지만, 그는 용기를 내어 진심을 전했다.'],
    stem: '㉠에 들어갈 말로 가장 알맞은 것을 고르십시오.',
    opts: ['감추기가', '잊어버리기가', '털어놓기가', '따져 보기가'],
    ans: 2,
    why: '마음을 고백하는 상황이므로, 속에 있는 생각을 솔직하게 말한다는 뜻의 "털어놓다"가 알맞아요.',
    vi: 'Ngày anh Sang-jun tỏ tình với người yêu là 19/10. Nơi anh chọn để tỏ tình là công viên Naksan ở Seoul. Việc thổ lộ tình cảm của mình với đối phương hẳn không dễ dàng, nhưng anh đã lấy hết dũng khí để nói lời thật lòng.',
    gloss: [['고백한', 'tỏ tình (고백하다)'], ['고백', 'lời tỏ tình'], ['선택한', 'đã chọn (선택하다)'], ['용기', 'dũng khí'], ['진심', 'tấm lòng thật']]
  },
  {
    head: '※ [3~4] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨가 즐겨 먹는 음식으로는 계란후라이, 치킨, 삼겹살이 꼽힌다. 반면에 가지와 피클은 그가 ㉠꺼리는 음식이다.'],
    stem: '밑줄 친 ㉠과 바꾸어 쓸 수 있는 것을 고르십시오.',
    opts: ['매우 즐기는', '싫어해서 피하는', '가끔 찾아 먹는', '처음 먹어 보는'],
    ans: 1,
    why: '"반면에"는 앞 문장과 반대되는 내용을 이어 줘요. 앞에서 좋아하는 음식을 말했으니, ㉠은 싫어한다는 뜻이에요. "꺼리다"는 싫어서 피한다는 뜻이에요.',
    vi: 'Các món anh Sang-jun thích ăn gồm trứng ốp la, gà rán và thịt ba chỉ nướng. Ngược lại, cà tím và dưa chuột muối chua là những món anh ngại ăn.',
    gloss: [['즐겨', 'thường hay, ưa thích'], ['꼽힌다', 'được kể đến, được nêu ra'], ['반면에', 'ngược lại'], ['꺼리는', 'ngại, né tránh']]
  },
  {
    head: '※ [3~4] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨의 취미는 크게 두 가지로 나뉜다. 하나는 온라인 게임인 \'리그 오브 레전드\'를 즐기는 것이고, 다른 하나는 인공지능의 도움을 받아 프로그램을 만드는 이른바 \'바이브 코딩\'이다. 전자가 이미 만들어진 게임을 즐기는 활동이라면, 후자는 새로운 것을 직접 만들어 내는 활동이라는 점에서 서로 구별된다.'],
    stem: '이 글의 중심 내용으로 가장 알맞은 것을 고르십시오.',
    opts: ['박상준 씨는 게임을 그만두고 프로그램을 만들기 시작했다.', '박상준 씨는 온라인 게임보다 운동을 더 좋아한다.', '박상준 씨는 인공지능이 게임을 대신해 주기를 바란다.', '박상준 씨의 취미는 게임을 즐기는 것과 바이브 코딩, 두 가지이다.'],
    ans: 3,
    why: '글의 첫 문장이 중심 문장이에요. 취미가 "두 가지"로 나뉘고, 그 두 가지가 게임(리그 오브 레전드)과 바이브 코딩이라고 설명하고 있어요.',
    vi: 'Sở thích của anh Sang-jun chia làm hai. Một là chơi game trực tuyến "League of Legends", hai là cái gọi là "vibe coding" – tạo ra chương trình với sự trợ giúp của AI. Điểm khác nhau là: cái trước là chơi một trò chơi đã có sẵn, còn cái sau là hoạt động tự tay tạo ra điều mới.',
    gloss: [['취미', 'sở thích'], ['나뉜다', 'được chia ra (나뉘다)'], ['인공지능', 'trí tuệ nhân tạo (AI)'], ['이른바', 'cái gọi là'], ['전자', 'cái trước (trong hai cái)'], ['후자', 'cái sau (trong hai cái)'], ['구별된다', 'được phân biệt']]
  },
  {
    head: '※ [5~6] 다음을 순서에 맞게 배열한 것을 고르십시오.',
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
    head: '※ [7~8] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨는 약속 시간에 자주 늦는 편이다. 그럴 때면 박상준 씨는 애창곡인 버즈의 \'남자를 몰라\'를 부르곤 하는데, 이 노래에는 \'매번 늦어도 이해할게\'라는 구절이 나온다. 이 구절을 들은 투이 씨는 웃으면서 그를 때린다.'],
    stem: '노래를 들은 투이 씨의 반응으로 알맞은 것을 고르십시오.',
    opts: ['화를 내며 자리를 떠난다.', '아무 말 없이 고개를 숙인다.', '노래를 따라 부르며 춤을 춘다.', '웃으면서 상준 씨를 때린다.'],
    ans: 3,
    why: '마지막 문장에 "웃으면서 그를 때린다"고 나와 있어요. 진짜 화가 난 것이 아니라 웃으면서 장난스럽게 때리는 거예요.',
    vi: '투이 hay đến muộn giờ hẹn. Những lúc như vậy, anh Sang-jun thường hát bài hát yêu thích của Buzz là "Namjareul molla" (남자를 몰라), trong đó có câu "dù lần nào cũng đến muộn anh vẫn thông cảm". Nghe câu đó, 투이 vừa cười vừa đánh anh.',
    gloss: [['약속', 'cuộc hẹn'], ['편이다', 'thuộc dạng, khá là…'], ['애창곡', 'bài hát yêu thích hay hát'], ['구절', 'câu, đoạn (trong bài hát, bài văn)'], ['때린다', 'đánh (때리다)']]
  },
  {
    head: '※ [7~8] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨에게 \'오늘 뭐 먹지?\'라고 물으면 돌아오는 대답은 번번이 같다. 바로 \'국물이 먹고 싶다\'는 것이다. 이처럼 어떤 질문에 대한 대답이 미리 정해져 있다시피 한 경우, 사람들은 질문을 던지기도 전에 대답을 짐작하기 마련이다.'],
    stem: '윗글을 통해 알 수 있는 것을 고르십시오.',
    opts: ['투이 씨는 메뉴를 물으면 늘 국물이 먹고 싶다고 답한다.', '투이 씨는 국물이 있는 음식을 먹지 않는다.', '투이 씨는 메뉴를 정할 때 상준 씨의 의견을 묻지 않는다.', '투이 씨는 질문을 받으면 대답을 오래 고민한다.'],
    ans: 0,
    why: '"대답은 번번이 같다"는 말은 항상 같은 대답을 한다는 뜻이에요. 그 대답이 "국물이 먹고 싶다"예요.',
    vi: 'Khi hỏi 투이 "hôm nay ăn gì?", câu trả lời lần nào cũng giống nhau. Đó là "em muốn ăn đồ có nước (canh)". Khi câu trả lời cho một câu hỏi gần như đã được định sẵn như vậy, người ta thường đoán được câu trả lời ngay cả trước khi đặt câu hỏi.',
    gloss: [['번번이', 'lần nào cũng'], ['국물', 'nước canh, nước dùng'], ['정해져', 'được định sẵn (정해지다)'], ['-다시피', 'gần như, hầu như'], ['짐작하기', 'đoán, phỏng đoán (짐작하다)'], ['-기 마련이다', 'chắc chắn sẽ…, vốn dĩ là…']]
  },
  {
    head: '※ [9~10] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨는 베트남 사람으로, 여러 과일 가운데에서도 망고를 특히 좋아한다. 이러한 취향에 착안하여 박상준 씨는 인공지능의 도움을 받아 \'망고게임\'을 직접 만들었다. 이 게임에는 리치, 람부탄, 용과 등 베트남에서 흔히 볼 수 있는 과일이 등장하며, 같은 과일끼리 합치다 보면 마지막에 망고가 완성된다.'],
    stem: '윗글의 내용과 다른 것을 고르십시오.',
    opts: ['투이 씨는 베트남 사람이다.', '박상준 씨가 망고게임을 만들었다.', '망고게임에는 베트남에서 흔한 과일이 나온다.', '투이 씨는 망고보다 두리안을 더 좋아한다.'],
    ans: 3,
    why: '"다른 것"을 찾는 문제예요. 글에서는 투이 씨가 망고를 "특히" 좋아한다고 했고, 두리안을 더 좋아한다는 말은 없어요.',
    vi: '투이 là người Việt Nam, trong các loại trái cây thì đặc biệt thích xoài. Dựa trên sở thích đó, anh Sang-jun đã nhờ AI hỗ trợ và tự tay làm "Trò chơi Xoài". Trong trò chơi có những loại trái cây thường thấy ở Việt Nam như vải, chôm chôm, thanh long…, và khi ghép các quả giống nhau lại thì cuối cùng quả xoài sẽ hoàn thành.',
    gloss: [['취향', 'sở thích, gu'], ['착안하여', 'dựa vào ý tưởng (착안하다)'], ['흔히', 'thường, phổ biến'], ['등장하며', 'xuất hiện (등장하다)'], ['합치다', 'gộp lại, ghép lại'], ['완성된다', 'được hoàn thành']]
  },
  {
    head: '※ [11~12] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 고양이를 좋아하는 반면, 투이 씨는 강아지를 좋아한다. ( ㉠ ) 두 사람이 함께 즐기는 게임에는 푸들과 고양이가 나란히 등장한다. ( ㉡ ) 게임을 만든 사람이 두 사람의 취향을 모두 반영하려 했기 때문이다. ( ㉢ )'],
    stem: '다음 문장이 들어갈 곳으로 알맞은 것을 고르십시오.\n〈보기〉 이는 우연이 아니다.',
    opts: ['㉠ 앞', '㉠', '㉡', '㉢'],
    ans: 2,
    why: '"이는"은 앞의 내용을 가리켜요. "푸들과 고양이가 나란히 등장한다"는 문장 뒤(㉡)에 "이는 우연이 아니다"가 오고, 그 이유가 이어져요.',
    vi: 'Anh Sang-jun thích mèo, còn 투이 thích chó. Trong trò chơi hai người cùng chơi, chó poodle và mèo xuất hiện cạnh nhau. (Điều này không phải ngẫu nhiên.) Đó là vì người làm game muốn phản ánh sở thích của cả hai.',
    gloss: [['-는 반면', 'trong khi đó, ngược lại'], ['나란히', 'song song, cạnh nhau'], ['등장한다', 'xuất hiện'], ['반영하려', 'định phản ánh (반영하다)']]
  },
  {
    head: '※ [11~12] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨는 박상준 씨가 음식을 먹는 모습이 카피바라 같다며 자주 ㉠놀린다. 카피바라는 남아메리카에 서식하는 설치류로, 느긋한 성격으로 알려져 있다. 그래서 박상준 씨는 게임 속에 당근을 먹고 있는 카피바라를 직접 등장시켰다.'],
    stem: '밑줄 친 ㉠의 뜻으로 가장 알맞은 것을 고르십시오.',
    opts: ['장난삼아 상대를 웃음거리로 삼는다.', '진지하게 상대를 칭찬한다.', '몰래 숨어서 상대를 지켜본다.', '큰 소리로 상대를 꾸짖는다.'],
    ans: 0,
    why: '"놀리다"는 장난으로 상대를 웃음거리로 만든다는 뜻이에요. 투이 씨는 칭찬이 아니라 웃기려고 장난으로 말하는 거예요.',
    vi: '투이 thường trêu rằng dáng anh Sang-jun ăn giống capybara. Capybara là loài gặm nhấm sống ở Nam Mỹ, nổi tiếng với tính cách thong thả. Vì vậy, anh Sang-jun đã tự tay đưa nhân vật capybara đang ăn cà rốt vào trong trò chơi.',
    gloss: [['놀린다', 'trêu chọc (놀리다)'], ['서식하는', 'sinh sống (서식하다)'], ['설치류', 'loài gặm nhấm'], ['느긋한', 'thong thả, thư thả'], ['등장시켰다', 'cho xuất hiện (등장시키다)']]
  },
  {
    head: '※ [13~14] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['투이 씨가 \'개구리 고기를 먹자\'고 제안하면 박상준 씨는 먹기 싫다고 답한다. 두 사람 사이에서 이 장면은 정해진 대화처럼 되풀이된다. 이러한 농담이 오가는 모습을 보면 두 사람이 서로 얼마나 가까운 사이인지 짐작할 수 있다.'],
    stem: '윗글에서 알 수 있는 두 사람의 관계로 가장 알맞은 것을 고르십시오.',
    opts: ['서로의 말에 한 번도 대답하지 않는 사이', '처음 만나 어색한 사이', '장난스러운 농담을 주고받을 만큼 가까운 사이', '의견이 달라 자주 다투는 사이'],
    ans: 2,
    why: '같은 농담이 되풀이된다는 것은 서로 편하게 장난을 칠 수 있다는 뜻이에요. 글의 마지막 문장도 "얼마나 가까운 사이인지 짐작할 수 있다"고 말하고 있어요.',
    vi: 'Khi 투이 đề nghị "mình ăn thịt ếch đi", anh Sang-jun trả lời là không muốn ăn. Cảnh này giữa hai người lặp đi lặp lại như một đoạn hội thoại cố định. Nhìn những câu đùa qua lại như vậy có thể đoán được hai người thân thiết với nhau đến mức nào.',
    gloss: [['제안하면', 'nếu đề nghị (제안하다)'], ['되풀이된다', 'được lặp đi lặp lại'], ['농담', 'lời đùa'], ['오가는', 'qua lại (오가다)'], ['짐작할', 'đoán (짐작하다)']]
  },
  {
    head: '※ [15~16] 다음 글을 읽고 물음에 답하십시오.',
    passage: ['박상준 씨는 카페에서 휴대전화나 노트북으로 가볍게 즐길 수 있는 게임을 연인과 함께하고 싶어 했다. 그래서 그는 인공지능과 대화를 주고받으며 게임을 직접 만들기로 했다. 이때 그가 활용한 방식이 이른바 \'바이브 코딩\'이다. 바이브 코딩이란 프로그램의 세부 문법을 일일이 입력하는 대신, 원하는 바를 말로 설명하여 인공지능이 코드를 작성하도록 하는 방식을 가리킨다.'],
    stem: '\'바이브 코딩\'에 대한 설명으로 알맞은 것을 고르십시오.',
    opts: ['원하는 것을 말로 설명하여 인공지능이 코드를 쓰게 하는 방식', '문법을 하나하나 직접 입력하여 프로그램을 만드는 방식', '다른 사람이 만든 게임을 그대로 내려받아 즐기는 방식', '카페에서 만난 사람들과 함께 프로그램을 만드는 방식'],
    ans: 0,
    why: '글의 마지막 문장에 정의가 나와 있어요. "세부 문법을 일일이 입력하는 대신" 말로 설명해서 인공지능이 코드를 쓰게 한다고 했어요. 그래서 ②는 반대 설명이에요.',
    vi: 'Anh Sang-jun muốn cùng người yêu chơi một trò chơi nhẹ nhàng bằng điện thoại hoặc laptop ở quán cà phê. Vì vậy anh quyết định vừa trò chuyện với AI vừa tự tay làm trò chơi. Cách anh dùng chính là cái gọi là "vibe coding". Vibe coding là cách mà thay vì gõ từng chi tiết cú pháp của chương trình, ta mô tả bằng lời điều mình muốn để AI viết mã.',
    gloss: [['가볍게', 'một cách nhẹ nhàng'], ['활용한', 'đã tận dụng (활용하다)'], ['이른바', 'cái gọi là'], ['세부', 'chi tiết'], ['일일이', 'từng cái một'], ['작성하도록', 'để viết ra (작성하다)'], ['가리킨다', 'chỉ ra, có nghĩa là (가리키다)']]
  }
];
