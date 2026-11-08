import request from './index'

// 本人在各场考试里的成绩。一次请求拿回全部，key 是考试 id。
// 以前"我的考试"页是每场考试发一次请求，几十场考试就要等好几分钟。
export const getMyScores = () => request.get('/exam-records/my-scores')
